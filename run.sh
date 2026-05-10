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
  service_demo       -> service_client or service_server
  action_demo        -> action_client or action_server

Examples:
  $0             # choose package interactively
  $0 hello_world_demo
  $0 topic_demo topic_sub
  $0 service_demo service_client
  $0 action_demo action_server
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
    service_demo)
      case "${exe}" in
        service_client)
          echo "请输入两个整数 (用空格分隔):"
          read -r a b
          if [[ -z "$a" || -z "$b" ]]; then
            echo "输入无效，请提供两个整数。" >&2
            exit 1
          fi
          ros2 run service_demo service_client "$a" "$b"
          ;;
        service_server)
          ros2 run service_demo service_server
          ;;
        "" )
          echo "Select executable for service_demo:"
          select choice in service_client service_server; do
            if [[ -n "${choice}" ]]; then
              if [[ "${choice}" == "service_client" ]]; then
                echo "请输入两个整数 (用空格分隔):"
                read -r a b
                if [[ -z "$a" || -z "$b" ]]; then
                  echo "输入无效，请提供两个整数。" >&2
                  exit 1
                fi
                ros2 run service_demo service_client "$a" "$b"
              else
                ros2 run service_demo "${choice}"
              fi
              break
            fi
          done
          ;;
        *)
          echo "Invalid executable for service_demo: ${exe}" >&2
          exit 1
          ;;
      esac
      ;;
    action_demo)
      case "${exe}" in
        action_client|action_server)
          ros2 run action_demo "${exe}"
          ;;
        "" )
          echo "Select executable for action_demo:"
          select choice in action_client action_server; do
            if [[ -n "${choice}" ]]; then
              ros2 run action_demo "${choice}"
              break
            fi
          done
          ;;
        *)
          echo "Invalid executable for action_demo: ${exe}" >&2
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
select pkg in hello_world_demo topic_demo service_demo action_demo; do
  if [[ -n "${pkg}" ]]; then
    run_package "${pkg}" ""
    break
  fi
  echo "无效选择，请重试。"
done