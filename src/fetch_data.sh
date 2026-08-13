#!/usr/bin/env bash
# Re-download the official BattLeDIM artefacts into data/raw/battledim_official.
#
# Source: the organisers' own repository (KIOS Research and Innovation Centre of
# Excellence, University of Cyprus). This is upstream, not a third-party mirror.
#
# The published SCADA CSVs live on Zenodo record 4017659 and on
# battledim.ucy.ac.cy. Both were unreachable when this study was run; see
# data/raw/PROVENANCE.json for the exact errors. This script fetches everything
# that IS reachable, which is enough to regenerate the SCADA with the official
# generator.
#
# The three .inp files are Git-LFS tracked. An anonymous clone yields 131-byte
# pointer stubs, so they are pulled individually from media.githubusercontent.com,
# which serves LFS-resolved content.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${REPO_ROOT}/data/raw/battledim_official"
COMMIT="ea81f544debb21587e09c32801ce605f8305720a"
UPSTREAM="https://github.com/KIOS-Research/BattLeDIM"
MEDIA="https://media.githubusercontent.com/media/KIOS-Research/BattLeDIM/master"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

mkdir -p "${DEST}/scoring_functions" "${DEST}/competition_leakages"

echo "==> cloning ${UPSTREAM} @ ${COMMIT}"
GIT_LFS_SKIP_SMUDGE=1 git clone --quiet "${UPSTREAM}" "${WORK}/battledim"
git -C "${WORK}/battledim" checkout --quiet "${COMMIT}"

echo "==> copying non-LFS artefacts"
cd "${WORK}/battledim"
cp "Dataset Generator/dataset_configuration.yalm" \
   "Dataset Generator/dataset_configuration_historical.yalm" \
   "Dataset Generator/dataset_configuration_evaluation.yalm" \
   "Dataset Generator/dataset_generator.py" \
   "Dataset Generator/README.txt" \
   "LICENSE.md" "${DEST}/"
cp "Scoring Algorithm/competition_data/leakages_info.yalm" \
   "Scoring Algorithm/Scoring_Algorithm.m" "${DEST}/"
cp "Scoring Algorithm/functions/"*.m           "${DEST}/scoring_functions/"
cp "Scoring Algorithm/competition_leakages/"*.xlsx "${DEST}/competition_leakages/"
git rev-parse HEAD > "${DEST}/SOURCE_COMMIT.txt"
git log -1 --format="%H %ci %s" >> "${DEST}/SOURCE_COMMIT.txt"

echo "==> fetching Git-LFS payloads file by file"
fetch_lfs() {
  local url_path="$1" out="$2"
  echo "    ${out}"
  curl --fail --silent --show-error --location --max-time 900 \
       --output "${DEST}/${out}" "${MEDIA}/${url_path}"
}
fetch_lfs "Dataset%20Generator/L-TOWN_v2_Real.inp"            "L-TOWN_v2_Real.inp"
fetch_lfs "Dataset%20Generator/L-TOWN_v2_Model.inp"           "L-TOWN_v2_Model.inp"
fetch_lfs "Scoring%20Algorithm/competition_data/L-TOWN.inp"   "L-TOWN.inp"

echo "==> verifying against the pinned digests"
cd "${DEST}"
sha256sum -c <<'SUMS'
0570538d93246d452e740316ffec66dabc17526b18c47384a083e76061551023  L-TOWN_v2_Real.inp
1b9ba161e3aebe02a916876d60c2126ee76f75e9f0d23c9ec4dfffd59cc0c366  L-TOWN_v2_Model.inp
6cc586edcb18d7aa094f653bf2e45608950559e7c1f151c96c80a67f635283e2  L-TOWN.inp
d74c6f2693ef81152d4aa4b4bca1b651f173edf50f8d5f702226d55a0f358790  dataset_configuration.yalm
19ac0fd99e7754d2e1df8af24dcdf21169c054c21fee1aaf64870ee8ec57ec96  dataset_configuration_historical.yalm
8780dda455f3c536e5283b6a2aa91deaad14430e4942976f05ef386e93fe8436  dataset_configuration_evaluation.yalm
e5086e2f9e39624f7178ba7fc017de6a3d99dd336ccc660f9dd95a2295c02895  leakages_info.yalm
dc4b8b08e6e37f34841473f5c2d7fffb7e189f4c2edbeed8cfface4701133f0f  dataset_generator.py
ab59f84cb633c07c3fc4d634d79085fa077db0bd17641d1ff563a2a698c9a584  Scoring_Algorithm.m
SUMS

echo "==> OK: official artefacts in ${DEST}"
