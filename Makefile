# Build the Docker image (uses your Dockerfile in the current directory)
make build

# Run the grinder: starts-with dead, ends-with beef, 8 workers, save results
make run PREFIX=dead SUFFIX=beef SCHEME=secp256k1 COUNT=2 WORKERS=8 OUT=results.jsonl

# Drop into a shell inside the image
make shell

# Remove the image
make clean

