#!/bin/bash
set -o xtrace
/etc/eks/bootstrap.sh ${cluster_name} \
  --kubelet-extra-args \
  '--node-labels=lifecycle=${lifecycle_label},sector=${sector_label},fleet=${fleet_name},pool_size=${pool_size},kind=${pool_kind} ${node_taints}'
