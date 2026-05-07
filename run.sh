#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

colcon build
source install/setup.bash

show_help() {
  cat <<EOF
Usage: $0 [package] [executable]

Run a ROS 2 package from this workspace.

Packages:
  hello_world_demo   -> hello_world
  topic_demo         -> topic_pub or topic_sub

Examples:
  $0             # choose package interactively
  $0 hello_world_demo
  $0 topic_demo topic_sub
EOF
}

run_package() {
  local pkg="$1"
  local exe="$2"

  case "${pkg}" in
    hello_world_demo)
      ros2 run hello_world_demo "${exe:-hello_world}"
      ;;
    topic_demo)
      case "${exe}" in
        topic_pub|topic_sub)
          ros2 run topic_demo "${exe}"
          ;;
        "" )
          echo "Select executable for topic_demo:"
          select choice in topic_pub topic_sub; do
            if [[ -n "${choice}" ]]; then
              ros2 run topic_demo "${choice}"
              break
            fi
          done
          ;;
        *)
          echo "Invalid executable for topic_demo: ${exe}" >&2
          exit 1
          ;;
      esac
      ;;
    *)
      echo "Unknown package: ${pkg}" >&2
      exit 1
      ;;
  esac
}

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  show_help
  exit 0
fi

if [[ -n "$1" ]]; then
  run_package "$1" "$2"
  exit 0
fi

PS3="请选择要运行的功能包 (输入编号)： "
select pkg in hello_world_demo topic_demo; do
  if [[ -n "${pkg}" ]]; then
    run_package "${pkg}" ""
    break
  fi
  echo "无效选择，请重试。"
done