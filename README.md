# Kluster Fleet Manager

[![build status](https://gitlab.com/rocket-boosters/kluster-fleet-manager/badges/main/pipeline.svg)](https://gitlab.com//rocket-boosters/kluster-fleet-manager/commits/main)
[![coverage report](https://gitlab.com//rocket-boosters/kluster-fleet-manager/badges/main/coverage.svg)](https://gitlab.com//rocket-boosters/kluster-fleet-manager/commits/main)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Code style: flake8](https://img.shields.io/badge/code%20style-flake8-white)](https://gitlab.com/pycqa/flake8)
[![Code style: mypy](https://img.shields.io/badge/code%20style-mypy-white)](http://mypy-lang.org/)

# Background

This is an alternative cluster autoscaler built for a specific purpose, which is to
autoscale EKS clusters utilizing EC2 fleets for node pools to handle big data workloads.

There exists a general
[Kubernetes Cluster Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler)
already that works well for a wide variety of cases. However, we encountered issues with
it while trying to run large-scale, resource-intensive data workloads. As such, we set
out to create an alternative suited to that purpose. This is not a rebuke of the great
work of those behind the general-purpose
[Kubernetes Cluster Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler).
It is instead a realization that one solution can't serve all purposes well and that we
would be better served in our case with a different implementation.

We are not alone in recognizing this. Atlassian has created
[Escalator](https://github.com/atlassian/escalator), which they describe as *a batch or 
job optimized horizontal autoscaler for Kubernetes*. That's exactly what
kluster-fleet-manager (KFM) is as well, although in our case we've been even less
general in our implementation. In our case, we also wanted an implementation that would
utilize spot pricing well for our fault-tolerant workloads.

The kluster-fleet-manager has been managing multiple production EKS clusters since 2018
and is considered stable. However, it is only recently that we've decided to open source
it for others to use.

# Implementation

*NOTE: As mentioned above, this cluster is specific and opinionated in how it operates.
Links are above for those interested in a more general-purpose solution without these
restrictions.*

Kluster fleet manager scales node resources for any number of EC2 fleets. Fleets must
be uniquely identified by a combination of:

- **sector**: A sector defines one or more fleets to schedule pods on. Simple clusters
  may have only one sector, but it is possible to have as many as you want. Pods must
  specify a `nodeSelector: { sector: "foo" }` to be considered part of this sector.
- **kind**: Can be one of `"memory"` or `"cpu"`. This specifies the types of EC2
  instances to include in the 
- **size**: Fleet size is specified by t-shirt size. See below for the resources
  available for each size.

For memory-optimized fleets, the available sizes and associated resources are:

|  size        |  CPU  |  Memory  |  Instance Options                                 |
|--------------|-------|----------|---------------------------------------------------|
|  **xsmall**  | 2     | 15.25Gi  | r5.large, r4.large, m5.xlarge, m4.xlarge          |
| **small**    | 4     | 30.5Gi   | r5.xlarge, r4.xlarge, m5.2xlarge, m4.2xlarge      |
| **medium**   | 8     | 61Gi     | r5.2xlarge, r4.2xlarge, m5.4xlarge, m4.4xlarge    |
| **large**    | 16    | 122Gi    | r5.4xlarge, r4.4xlarge, m5.8xlarge, m4.10xlarge   |
| **xlarge**   | 32    | 244Gi    | r5.8xlarge, r4.8xlarge, m5.16xlarge, m4.16xlarge  |

For cpu-optimized fleets, the available sizes and associated resources are:

|  size        |  CPU  |  Memory  |  Instance Options                                 |
|--------------|-------|----------|---------------------------------------------------|
| **xsmall**   | 4     | 7.5Gi    | c5.xlarge, c4.xlarge, m5.xlarge, m4.xlarge        |
| **small**    | 8     | 15Gi     | c5.2xlarge, c4.2xlarge, m5.2xlarge, m4.2xlarge    |
| **medium**   | 16    | 30Gi     | c5.4xlarge, c4.4xlarge, m5.4xlarge, m4.4xlarge    |
| **large**    | 36    | 60Gi     | c5.9xlarge, c4.8xlarge, m5.12xlarge, m4.10xlarge  |
| **xlarge**   | 64    | 144Gi    | c5.18xlarge, m5.16xlarge, m4.16xlarge             |

# Usage

## 1. Terraform Fleets

Given an already defined or created EKS cluster, fleets can be created for that EKS
cluster using the `eks_fleet` module in this repo. An example of using that module
would look something like this:

```terraform
module "fleet" {
  source   = "./terraform/eks_fleet"

  # Name of the EKS cluster that will own the nodes in this fleet.
  cluster_name = var.cluster_name

  # Fleets can be either spot by default or on-demand by default. Spot nodes are a great
  # option for fault-tolerant workloads.
  spot = true

  # Each fleet must reside in a sector and specify its t-shirt node size.
  sector_label   = "foo"
  node_pool_size = "small"

  # All fleets in a sector should be of the same kind, either "memory" or "cpu".
  node_pool_kind = "memory"
  
  # Make sure that any fleets where resources are needed to bootstrap the cluster are
  # set greater than zero.
  initial_node_count = 1
  
  # Find the AMI for your nodes at:
  # https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html
  ami                = var.eks_ami

  # The default can be used here. We've often raised it to 50 for cases with high
  # cardinality in container images where a lot of layer storage is needed. 
  ebs_size           = var.ebs_size

  # These are needed to locate the the nodes in your network.
  security_group_id  = var.outbound_security_group_id
  private_subnet_ids = var.private_subnet_ids
  
  # Per-node configuration settings
  ssh_key_name       = var.ssh_key_name
  instance_profile_name = var.cluster_node_instance_profile_name

  # Add additional tags to the fleet resources, including the nodes as EC2 tags.
  # Be careful not to use any of the following reserved keys:
  # - Name
  # - Spot
  # - kubernetes.io/cluster/${var.cluster_name}
  # - cluster
  # - fleet
  # - sector
  # - kind
  # - size
  # as they are already set based on the other configuration in the fleet.
  tags = {
    environment = var.environment
  }
}
```

In this example a fleet has been created in the `"foo"` sector and will consist of
small, memory-optimized EC2 instances. Notice the initial node count is set to 1 here,
which means the fleet will launch with an active node.

If you want to schedule the kluster-fleet-manager on a fleet node, you will need to have
that capacity included in the launch node count.

Create as many of these fleets as you need for your use case. New fleets can be added
at any time. However, each fleet must have a unique sector + size value. Also, all
fleets in a sector should be of the same kind to optimize resource allocation.

## 2. Define Configuration

A running kluster-fleet-manager process must be configured using a yaml file. This
can be built into an image, but the recommended approach is to mount this file as a
volume from a ConfigMap resource.

A configuration might look something like this:

```yaml
# How many seconds to sleep between each resize operation.
sleep_interval: 20
# % of key resources (CPU or Memory) to oversubscribe when allocating resources. This
# should always be >0 to give enough slack for cases where inefficient kube system
# allocations might prevent blocking problems. We've found 0.2 works well, but in some
# cases we like to make this even higher for transient workloads that suggest additional
# work is on the way, e.g. CI/CD pipelines.
default_over_subscription: 0.2
# Number of CPUs per node to reserve for allocation to Daemonsets and other per-node
# resources that are not included in the autoscaling resource pool. This is specified
# in the same format as the kubernetes pod resource.cpu requirements are specified.
reserved_cpus: 1.0
# Amount of memory to reserve on each node for non-scaled resources, e.g. Daemonset
# pods. This is specified in the same format as the kubernetes pod resource.memory
# requirements are specified.
reserved_memory: 2.5Gi
# Here the sectors are defined along with the fleets within them.
sectors:
  coordinate:
    # In this case there is a coordinate sector that only has a small fleet. In this
    # specific case the coordinate sector houses long-running control resources,
    # including the kluster-fleet-manager deployment as well as private CI runners. 
    # It has a min_capacity of 2 to indicate that there should always be at least two
    # nodes running in this fleet. There can be more, but never less. Here that serves
    # the purpose of ensuring that excess slack is always available to reduce any
    # possible
    kind: memory
    fleets:
    - size: small
      min_capacity: 2
  primary:
    # The rest of the cluster in this case uses the primary sector, which has three
    # fleets in the small, medium and large sizes.
    kind: memory
    fleets:
    - size: small
      min_capacity: 0
    - size: medium
      min_capacity: 0
    - size: large
      min_capacity: 0
```

## 3. Deploy kluster-fleet-manager

The [install.yaml](install.yaml) defines a working installation for a
kluster-fleet-manager within an EKS cluster. Replace the `data."config.yaml"` value
in the `kluster-fleet-manager-config` with the config defined in the previous step
and then deploy that modified configuration into your cluster.

The [install.yaml](install.yaml) includes cluster role that has read-only access to pods
in every namespace in the cluster. Similarly, it has read/write permissions to the nodes
in the cluster.
