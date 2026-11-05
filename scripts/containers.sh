#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null || {
    echo 'Docker ausente.' >&2
    exit 3
}
docker info >/dev/null
while read -r name adapter image; do
    [[ -z "$name" || "$name" == \#* ]] && continue
    docker build --file tests/Containerfile --build-arg "BASE_IMAGE=$image" --build-arg "ADAPTER=$adapter" --tag "foundry-test:$name" .
    docker run --rm --network none "foundry-test:$name"
done <tests/containers.tsv
