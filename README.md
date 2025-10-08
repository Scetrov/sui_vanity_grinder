# Sui Vanity Address Grinder

A fast, **multi-core** vanity address generator for the **Sui** blockchain.  
It supports **Ed25519**, **Secp256k1**, and **Secp256r1 (P‑256)**, searches for **prefixes** and/or **suffixes** in the Sui address, and exports **importable Bech32 private keys** with the `suiprivkey` prefix.

> ⚠️ **Security**: Run offline on a trusted machine. Never share your private keys. Back them up securely.

---

## How It Works

Sui addresses are derived as:
```
address = 0x || blake2b-256( scheme_flag || public_key_bytes )
```
where `scheme_flag` is one of:
- `0x00` — Ed25519
- `0x01` — Secp256k1
- `0x02` — Secp256r1

This tool brute‑forces random keypairs until the address hex (after `0x`) matches your desired **prefix** and/or **suffix**.

It also exports the private key as **Bech32**:
```
suiprivkey1<bech32-encoded( flag || 32-byte-private-key )>
```
which can be imported into Sui tooling that supports the `suiprivkey` format.

---

## Features
- 🔀 **Schemes**: `ed25519`, `secp256k1`, `secp256r1`
- ⚙️ **Multi-core**: uses Python `multiprocessing` (one process per worker)
- 🎯 **Matching**: `--prefix` and/or `--suffix` (hex, case-insensitive)
- 📤 **Export**: importable `suiprivkey…` (Bech32), plus raw hex for debugging
- 📄 **Output**: JSON Lines (one result per line), optional file via `--out`
- 🖥️ **Docker + Makefile** included

---

## Quick Start (Local)

```bash
# 1) Install dependencies
pip install pynacl coincurve cryptography

# 2) Run (prefix example)
python sui_vanity_grinder.py --scheme ed25519 --prefix cafe

# 3) Run (prefix + suffix)
python sui_vanity_grinder.py --scheme secp256k1 --prefix dead --suffix beef --count 2 --workers 8 --out results.jsonl
```

### Output (one JSON line per hit)
```json
{
  "scheme": "ed25519",
  "address": "0xdead...beef",
  "suiprivkey": "suiprivkey1q....",
  "private_key_hex": "3f6e...",
  "public_key_hex": "a1b2...",
  "matched_prefix": "dead",
  "matched_suffix": "beef",
  "timestamp": 1738690000
}
```

> Use the `suiprivkey` field for importing the private key into Sui-compatible tools. The `private_key_hex` is provided for debugging only.

---

## Docker

A minimal Dockerfile is provided.

```bash
# Build
docker build -t sui-vanity .

# Run (mount current dir to capture --out file)
docker run --rm -v "$PWD":/data sui-vanity \
  --scheme secp256k1 --prefix dead --suffix beef --count 2 --workers 8 --out /data/results.jsonl
```

### Makefile (Convenience)
```bash
# Build image
make build

# Run with parameters
make run PREFIX=dead SUFFIX=beef SCHEME=secp256k1 COUNT=2 WORKERS=8 OUT=results.jsonl

# Shell inside the image
make shell
```

---

## CLI

```
usage: sui_vanity_grinder.py [-h] [--scheme {ed25519,secp256k1,secp256r1}]
                             [--prefix PREFIX] [--suffix SUFFIX]
                             [--count COUNT] [--workers WORKERS]
                             [--out OUT] [--no-progress]
```

**Options**
- `--scheme`   Curve/scheme (`ed25519` | `secp256k1` | `secp256r1`). Default: `ed25519`
- `--prefix`   Hex prefix to match (without `0x`), e.g. `cafe`
- `--suffix`   Hex suffix to match (without `0x`), e.g. `beef` or `00`
- `--count`    Number of matches to find before exiting. Default: `1`
- `--workers`  Worker processes (defaults to CPU core count)
- `--out`      Append JSONL results to this file
- `--no-progress`  Disable periodic speed updates

---

## Tips & Performance

- **Difficulty** grows exponentially: a hex prefix of length *n* matches with probability `1/16^n`.  
  Combining prefix and suffix of lengths *n* and *m* is approximately `1/16^(n+m)`.
- Start small (e.g., 3–5 hex chars) to verify setup and approximate throughput.
- Increase `--workers` up to your logical core count.
- Prefer running **offline** (air‑gapped is best) and back up winning keys immediately.

> GPU acceleration: possible but non-trivial (due to key generation on curves and hashing). If needed, you can offload the BLAKE2b inner loop via CUDA/OpenCL and keep keygen on CPU; open an issue or PR for this.

---

## Project Structure
```
.
├── sui_vanity_grinder.py  # main utility
├── Dockerfile             # minimal Python 3.12-slim image
└── Makefile               # build/run helpers
```

---

## License
MIT — © Richard Slater
