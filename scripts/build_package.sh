#!/bin/bash
set -e

# Default values
SERVICE="mock"
PYTHON_VERSION="3.11"
GIT_REF=$(git rev-parse HEAD 2>/dev/null || echo "local")
WORK_DIR=""
EXCLUDES=""
RELEASE_VERSION=""
ORIGINAL_DIR=$(pwd)
OUTPUT_FILE=""
SERVICE_DIR="."

function show_help {
  echo "Usage: $0 [options]"
  echo ""
  echo "Build a release package for deployment"
  echo ""
  echo "Options:"
  echo "  -s, --service SERVICE      Service name (default: mock)"
  echo "  -v, --version VERSION      Release version (REQUIRED)"
  echo "  -g, --git-ref REF          Git reference (default: current HEAD)"
  echo "  -p, --python VERSION       Python version (default: 3.11)"
  echo "  -e, --excludes LIST        Comma-separated list of paths to exclude"
  echo "  -o, --output FILE          Output file name (REQUIRED)"
  echo "  -d, --service-dir DIR      Service directory (default: current directory)"
  echo "  -h, --help                 Display this help message"
  echo ""
  echo "Example:"
  echo "  $0 --version v1.0.0 --output mypackage.tar.gz"
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -s|--service)
      SERVICE="$2"
      shift 2
      ;;
    -v|--version)
      RELEASE_VERSION="$2"
      shift 2
      ;;
    -g|--git-ref)
      GIT_REF="$2"
      shift 2
      ;;
    -p|--python)
      PYTHON_VERSION="$2"
      shift 2
      ;;
    -e|--excludes)
      EXCLUDES="$2"
      shift 2
      ;;
    -o|--output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -d|--service-dir)
      SERVICE_DIR="$2"
      shift 2
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

if [ -z "$RELEASE_VERSION" ]; then
  echo "ERROR: Release version is required. Use --version to set it."
  show_help
  exit 1
fi

if [ -z "$OUTPUT_FILE" ]; then
  echo "ERROR: Output file name is required. Use --output to set it."
  show_help
  exit 1
fi

WORK_DIR="/tmp/package-${SERVICE}"

echo "Creating release package with the following settings:"
echo "  Service:         ${SERVICE}"
echo "  Version:         ${RELEASE_VERSION}"
echo "  Git ref:         ${GIT_REF}"
echo "  Python:          ${PYTHON_VERSION}"
echo "  Output:          ${OUTPUT_FILE}"
echo "  Excluded paths:  ${EXCLUDES}"
echo "  Service dir:     ${SERVICE_DIR}"

# Create a clean working directory
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"

# Copy service files from the specified service directory
cp -r "${SERVICE_DIR}"/* "${WORK_DIR}/"

if [ -f "${WORK_DIR}/version.json" ]; then
    echo "Updating version.json..."
    jq --arg release_version "${RELEASE_VERSION}" --arg git_ref "${GIT_REF}" \
        '.release_version = $release_version | .git_ref = $git_ref' "${WORK_DIR}/version.json" > "${WORK_DIR}/version_new.json"
    mv "${WORK_DIR}/version_new.json" "${WORK_DIR}/version.json"
fi

echo "Creating archive ${OUTPUT_FILE}..."
# Create an empty file to avoid tar errors
touch "${WORK_DIR}/source.tar.gz"

EXCLUDE_FLAGS=""
IFS=',' read -ra EXCLUDE_ARRAY <<< "$EXCLUDES"
for item in "${EXCLUDE_ARRAY[@]}"; do
    EXCLUDE_FLAGS="${EXCLUDE_FLAGS} --exclude=${item}"
done

tar ${EXCLUDE_FLAGS} -zcvf "${ORIGINAL_DIR}/${OUTPUT_FILE}" -C "${WORK_DIR}" .
echo "You can inspect the contents with: tar -tvf ${ORIGINAL_DIR}/${OUTPUT_FILE}"

