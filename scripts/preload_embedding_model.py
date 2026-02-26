#!/usr/bin/env python
"""
Pre-download the fastembed model for Duro MCP server.
Run this ONCE before starting Claude Code to cache the model.

Usage:
    python preload_embedding_model.py
"""
import os
import sys
import time

# Set cache paths BEFORE importing fastembed
os.environ["FASTEMBED_CACHE_PATH"] = r"C:\Users\sibag\.cache\fastembed"
os.environ["HF_HOME"] = r"C:\Users\sibag\.cache\huggingface"

# Ensure cache directories exist
os.makedirs(os.environ["FASTEMBED_CACHE_PATH"], exist_ok=True)
os.makedirs(os.environ["HF_HOME"], exist_ok=True)

print(f"FASTEMBED_CACHE_PATH: {os.environ['FASTEMBED_CACHE_PATH']}")
print(f"HF_HOME: {os.environ['HF_HOME']}")

MODEL_NAME = "BAAI/bge-small-en-v1.5"

print(f"\nDownloading and caching model: {MODEL_NAME}")
print("This may take a few minutes on first run...\n")

start = time.time()

try:
    from fastembed import TextEmbedding

    print("Loading model...")
    model = TextEmbedding(model_name=MODEL_NAME)

    print("Warming up model...")
    _ = list(model.embed(["test embedding for warmup"]))

    elapsed = time.time() - start
    print(f"\nModel loaded and cached in {elapsed:.1f}s")
    print("You can now restart Claude Code - Duro will start much faster.")

except Exception as e:
    print(f"\nError: {e}")
    sys.exit(1)

# Verify cache was created
print("\nVerifying cache...")
cache_path = os.environ["FASTEMBED_CACHE_PATH"]
if os.path.exists(cache_path):
    files = os.listdir(cache_path)
    print(f"Cache directory has {len(files)} items: {files[:5]}...")
else:
    print("WARNING: Cache directory not created!")
