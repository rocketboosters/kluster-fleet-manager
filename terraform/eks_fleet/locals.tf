locals {
  fleet_name = "${var.sector_label}-${var.node_pool_size}"
  name       = "${var.cluster_name}-${local.fleet_name}"

  # These are the standard labels suggested in AWS docs, including:
  # https://aws.amazon.com/blogs/compute/cost-optimization-and-resilience-eks-with-spot-instances/
  lifecycle_label = var.spot ? "Ec2Spot" : "OnDemand"

  size_pools = {
    xsmall_memory : [
      { type: "r4.large", max_price: "0.133" },
      { type: "r5.large", max_price: "0.126" },
      { type: "m4.xlarge", max_price: "0.200" },
      { type: "m5.xlarge", max_price: "0.192" },
    ],
    xsmall_cpu : [
      { type: "c4.xlarge", max_price: "0.199" },
      { type: "c5.xlarge", max_price: "0.170" },
      { type: "m4.xlarge", max_price: "0.200" },
      { type: "m5.xlarge", max_price: "0.192" },
    ]
    small_memory : [
      { type : "r4.xlarge", max_price : "0.266" },
      { type : "r5.xlarge", max_price : "0.252" },
      { type : "m4.2xlarge", max_price : "0.400" },
      { type : "m5.2xlarge", max_price : "0.384" },
    ]
    small_cpu : [
      { type: "c4.2xlarge", max_price: "0.398" },
      { type: "c5.2xlarge", max_price: "0.340" },
      { type: "m4.2xlarge", max_price: "0.400" },
      { type: "m5.2xlarge", max_price: "0.384" },
    ]
    medium_memory : [
      { type : "r4.2xlarge", max_price : "0.532" },
      { type : "r5.2xlarge", max_price : "0.504" },
      { type : "m4.4xlarge", max_price : "0.800" },
      { type : "m5.4xlarge", max_price : "0.768" },
    ]
    medium_cpu : [
      { type: "c4.4xlarge", max_price: "0.796" },
      { type: "c5.4xlarge", max_price: "0.680" },
      { type: "m4.4xlarge", max_price: "0.800" },
      { type: "m5.4xlarge", max_price: "0.768" },
    ]
    large_memory : [
      { type : "r4.4xlarge", max_price : "1.064" },
      { type : "r5.4xlarge", max_price : "1.008" },
      { type : "m4.10xlarge", max_price : "2.000" },
      { type : "m5.8xlarge", max_price : "1.536" },
    ]
    large_cpu : [
      { type: "c4.8xlarge", max_price: "1.591" },
      { type: "c5.9xlarge", max_price: "1.530" },
      { type: "m4.10xlarge", max_price: "2.000" },
      { type: "m5.12xlarge", max_price: "2.304" },
    ]
    xlarge_memory : [
      { type: "r4.8xlarge", max_price: "2.128" },
      { type: "r5.8xlarge", max_price: "2.016" },
      { type: "m4.16xlarge", max_price: "3.200" },
      { type: "m5.16xlarge", max_price: "3.072" },
    ]
    xlarge_cpu : [
      { type: "c5.18xlarge", max_price: "3.060" },
      { type: "m4.16xlarge", max_price: "3.200" },
      { type: "m5.16xlarge", max_price: "3.072" },
    ]
  }

  node_pool = local.size_pools["${var.node_pool_size}_${var.node_pool_kind}"]

  subnets = [for az, id in var.private_subnet_ids : tomap({
    az = az,
    id = id
  })]

  overrides = {
    for item in setproduct(local.subnets, local.node_pool) :
    join("-", [item[0]["id"], item[1]["type"]]) => {
      subnet : { "id" : item[0]["id"], "availability_zone" : item[0]["az"] }
      spec : item[1]
    }
  }
}
