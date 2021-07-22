resource "aws_launch_template" "fleet" {
  name                                 = local.name
  image_id                             = var.ami
  instance_initiated_shutdown_behavior = "terminate"
  key_name                             = var.ssh_key_name

  iam_instance_profile {
    name = var.instance_profile_name
  }

  vpc_security_group_ids = [var.security_group_id]

  user_data = base64encode(data.template_file.bootstrap.rendered)

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = var.ebs_size
      volume_type           = "gp2"
      delete_on_termination = true
    }
  }

  tags = merge(var.tags, tomap({
    cluster     = var.cluster_name
    fleet       = local.fleet_name
    sector      = var.sector_label
    size        = var.node_pool_size
    kind        = var.node_pool_kind
    name        = local.name
    managed     = "terraform"
  }))

  tag_specifications {
    resource_type = "instance"

    tags = merge(var.tags, tomap({
      Name = local.name
      Spot = true
      "kubernetes.io/cluster/${var.cluster_name}" = "owned"
      cluster = var.cluster_name
      fleet = local.fleet_name
      sector = var.sector_label
      kind = var.node_pool_kind
      size = var.node_pool_size
    }))
  }
}

resource "aws_ec2_fleet" "fleet" {
  // Do not terminate excess capacity. The autoscaler will handle
  // that more gracefully.
  excess_capacity_termination_policy = "no-termination"
  terminate_instances                = true
  replace_unhealthy_instances        = true
  type                               = "maintain"

  spot_options {
    allocation_strategy         = "lowestPrice"
    instance_pools_to_use_count = 2
  }

  target_capacity_specification {
    default_target_capacity_type = var.spot ? "spot" : "on-demand"
    total_target_capacity = var.initial_node_count
  }

  tags = merge(var.tags, tomap({
    Name        = local.name
    cluster     = var.cluster_name
    fleet       = local.fleet_name
    sector      = var.sector_label
    kind        = var.node_pool_kind
    size        = var.node_pool_size
    name        = local.name
    managed     = "terraform"
  }))

  lifecycle {
    ignore_changes = [target_capacity_specification]
  }

  launch_template_config {
    launch_template_specification {
      version            = aws_launch_template.fleet.latest_version
      launch_template_id = aws_launch_template.fleet.id
    }

    dynamic "override" {
      for_each = local.overrides

      content {
        availability_zone = override.value["subnet"]["availability_zone"]
        instance_type     = override.value["spec"]["type"]
        max_price         = override.value["spec"]["max_price"]
        subnet_id         = override.value["subnet"]["id"]
        weighted_capacity = 1
        priority          = 0
      }
    }
  }
}
