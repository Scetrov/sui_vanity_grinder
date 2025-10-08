
#!/usr/bin/env python3
"""
sui_vanity_grinder.py

Multi-core vanity address finder for Sui.
- Supports Ed25519, Secp256k1, Secp256r1 (schemes 0x00, 0x01, 0x02)
- Uses BLAKE2b-256 over (scheme_flag || public_key_bytes) to form the Sui address
- Parallelizes across CPU cores
- Matches a hex prefix and/or suffix AFTER the "0x" (case-insensitive).
- Exports Sui-importable **Bech32** private keys with the "suiprivkey" HRP per SIP-15.

USAGE EXAMPLES
--------------
Find one Ed25519 address starting with "cafe":
    python sui_vanity_grinder.py --prefix cafe --scheme ed25519

Find one Secp256k1 address that ends with "beef":
    python sui_vanity_grinder.py --scheme secp256k1 --suffix beef

Require both: starts with "dead" AND ends with "beef":
    python sui_vanity_grinder.py --prefix dead --suffix beef --scheme secp256r1

Find two matches using 12 workers and save to JSONL:
    python sui_vanity_grinder.py --prefix babe --count 2 --workers 12 --out results.jsonl

SECURITY
--------
* Run offline on a trusted machine.
* NEVER paste or upload the private keys anywhere.
* Prefer strong OS entropy sources. Keys are generated locally and never leave this process.
"""
import argparse
import base64
import hashlib
import json
import multiprocessing as mp
import os
import queue
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional

# --- Optional crypto backends ---
# Install:
#   pip install pynacl coincurve cryptography
try:
    from nacl.signing import SigningKey as Ed25519SigningKey
    HAVE_NACL = True
except Exception:
    HAVE_NACL = False

try:
    import coincurve
    HAVE_COINCURVE = True
except Exception:
    HAVE_COINCURVE = False

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    HAVE_CRYPTOGRAPHY = True
except Exception:
    HAVE_CRYPTOGRAPHY = False


SCHEME_FLAGS = {
    "ed25519": b"\x00",
    "secp256k1": b"\x01",
    "secp256r1": b"\x02",
}

# ------------------------
# Minimal Bech32 (BIP-0173) encoder for "suiprivkey"
# ------------------------
CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def _bech32_polymod(values):
    GENERATORS = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        b = (chk >> 25) & 0xFF
        chk = ((chk & 0x1ffffff) << 5) ^ v
        for i in range(5):
            chk ^= GENERATORS[i] if ((b >> i) & 1) else 0
    return chk

def _bech32_hrp_expand(hrp: str):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]

def _bech32_create_checksum(hrp: str, data):
    values = _bech32_hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]

def _bech32_encode(hrp: str, data) -> str:
    combined = data + _bech32_create_checksum(hrp, data)
    return hrp + '1' + ''.join([CHARSET[d] for d in combined])

def _convertbits(data: bytes, frombits: int, tobits: int, pad: bool = True) -> Optional[list[int]]:
    """General power-of-2 base conversion. Returns list of 5-bit groups."""
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for b in data:
        if b < 0 or (b >> frombits):
            return None
        acc = ((acc << frombits) | b) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret

def encode_sui_privkey(flag_and_key: bytes) -> str:
    """Encode 33 bytes (flag||privkey) to Bech32 with HRP 'suiprivkey'."""
    hrp = "suiprivkey"
    data = _convertbits(flag_and_key, 8, 5, True)
    if data is None:
        raise ValueError("convertbits failed")
    return _bech32_encode(hrp, data)

# ------------------------


@dataclass
class Keypair:
    scheme: str
    private_key_hex: str     # 32-byte raw private key in hex
    public_key_hex: str      # 32B (ed25519) or 33B compressed (secp*)
    address: str             # "0x" + 64 hex chars
    suiprivkey: str          # Bech32 "suiprivkey1..." (flag||privkey)


def _to_address(scheme: str, pubkey_bytes: bytes) -> str:
    """Derive Sui address from scheme flag + public key bytes via blake2b-256."""
    flag = SCHEME_FLAGS[scheme]
    digest = hashlib.blake2b(flag + pubkey_bytes, digest_size=32).hexdigest()
    return "0x" + digest


def _gen_ed25519() -> Keypair:
    if not HAVE_NACL:
        raise RuntimeError("Ed25519 requires pynacl. Install with: pip install pynacl")
    sk = Ed25519SigningKey.generate()
    vk = sk.verify_key
    pub = bytes(vk)  # 32 bytes
    addr = _to_address("ed25519", pub)
    seed32 = sk.encode()  # 32-byte seed
    sui_b32 = encode_sui_privkey(SCHEME_FLAGS["ed25519"] + seed32)
    return Keypair("ed25519", seed32.hex(), pub.hex(), addr, sui_b32)


def _gen_secp256k1() -> Keypair:
    if not HAVE_COINCURVE:
        raise RuntimeError("Secp256k1 requires coincurve. Install with: pip install coincurve")
    pk = coincurve.PrivateKey()  # random 32 bytes
    pub = pk.public_key.format(compressed=True)  # 33 bytes
    addr = _to_address("secp256k1", pub)
    raw32 = pk.secret  # 32 bytes
    sui_b32 = encode_sui_privkey(SCHEME_FLAGS["secp256k1"] + raw32)
    return Keypair("secp256k1", raw32.hex(), pub.hex(), addr, sui_b32)


def _gen_secp256r1() -> Keypair:
    if not HAVE_CRYPTOGRAPHY:
        raise RuntimeError("Secp256r1 requires cryptography. Install with: pip install cryptography")
    sk = ec.generate_private_key(ec.SECP256R1())
    pub = sk.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.CompressedPoint,
    )  # 33 bytes
    addr = _to_address("secp256r1", pub)
    priv_int = sk.private_numbers().private_value
    raw32 = priv_int.to_bytes(32, "big")
    sui_b32 = encode_sui_privkey(SCHEME_FLAGS["secp256r1"] + raw32)
    return Keypair("secp256r1", raw32.hex(), pub.hex(), addr, sui_b32)


GEN_MAP: dict[str, Callable[[], Keypair]] = {
    "ed25519": _gen_ed25519,
    "secp256k1": _gen_secp256k1,
    "secp256r1": _gen_secp256r1,
}


def worker(scheme: str, prefix: str | None, suffix: str | None,
           results_q: mp.Queue, stop_event: mp.Event, report_every: int = 10_000):
    gen = GEN_MAP[scheme]
    pref = prefix.lower() if prefix else None
    suf = suffix.lower() if suffix else None
    checked = 0
    t0 = time.time()
    while not stop_event.is_set():
        kp = gen()
        h = kp.address[2:]  # strip 0x
        ok = True
        if pref and not h.startswith(pref):
            ok = False
        if ok and suf and not h.endswith(suf):
            ok = False
        if ok:
            try:
                results_q.put(kp, block=False)
            except queue.Full:
                pass
        checked += 1
        if checked % report_every == 0:
            t1 = time.time()
            speed = checked / max(1e-9, (t1 - t0))
            try:
                results_q.put(("stats", os.getpid(), int(speed)))
            except queue.Full:
                pass


def main():
    parser = argparse.ArgumentParser(description="Multi-core Sui vanity address finder")
    parser.add_argument("--scheme", choices=["ed25519", "secp256k1", "secp256r1"], default="ed25519")
    parser.add_argument("--prefix", help="Hex prefix to match (without 0x). Example: cafe or deadbeef")
    parser.add_argument("--suffix", help="Hex suffix to match (without 0x). Example: beef or 00")
    parser.add_argument("--count", type=int, default=1, help="How many matches to find before stopping.")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1, help="Number of worker processes.")
    parser.add_argument("--out", type=str, default=None, help="Output JSONL file to append results.")
    parser.add_argument("--no-progress", action="store_true", help="Disable periodic speed updates.")
    args = parser.parse_args()

    if not args.prefix and not args.suffix:
        print("Error: provide at least one of --prefix or --suffix", file=sys.stderr)
        sys.exit(2)

    # Validate hex-ness
    if args.prefix:
        try:
            int(args.prefix, 16)
        except ValueError:
            print("Error: --prefix must be hexadecimal [0-9a-f].", file=sys.stderr)
            sys.exit(2)
    if args.suffix:
        try:
            int(args.suffix, 16)
        except ValueError:
            print("Error: --suffix must be hexadecimal [0-9a-f].", file=sys.stderr)
            sys.exit(2)

    if args.workers < 1:
        print("Error: --workers must be >= 1", file=sys.stderr)
        sys.exit(2)

    out_f = open(args.out, "a", encoding="utf-8") if args.out else None

    mgr = mp.Manager()
    results_q: mp.Queue = mgr.Queue(maxsize=1000)
    stop_event = mgr.Event()

    procs = []
    for _ in range(args.workers):
        p = mp.Process(target=worker, args=(args.scheme, args.prefix, args.suffix, results_q, stop_event))
        p.daemon = True
        p.start()
        procs.append(p)

    found = 0
    last_stat = {}
    try:
        while found < args.count:
            try:
                item = results_q.get(timeout=1.0)
            except queue.Empty:
                continue
            if isinstance(item, tuple) and item and item[0] == "stats":
                if not args.no_progress:
                    _, pid, speed = item
                    last_stat[pid] = speed
                    total = sum(last_stat.values())
                    print(f"[stats] ~{total:,} keys/sec across {len(last_stat)} workers", end="\r", flush=True)
                continue

            kp: Keypair = item
            found += 1
            rec = {
                "scheme": kp.scheme,
                "address": kp.address,
                "suiprivkey": kp.suiprivkey,            # Bech32-encoded, importable
                "private_key_hex": kp.private_key_hex,  # raw 32B for debugging
                "public_key_hex": kp.public_key_hex,
                "matched_prefix": args.prefix.lower() if args.prefix else None,
                "matched_suffix": args.suffix.lower() if args.suffix else None,
                "timestamp": int(time.time()),
            }
            line = json.dumps(rec)
            print("\nFOUND:", line, flush=True)
            if out_f:
                out_f.write(line + "\n")
                out_f.flush()

        stop_event.set()

    except KeyboardInterrupt:
        print("\nInterrupted, stopping workers...")
        stop_event.set()
    finally:
        for p in procs:
            p.join(timeout=2.0)
        if out_f:
            out_f.close()


if __name__ == "__main__":
    main()
