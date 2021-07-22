data "template_file" "bootstrap" {
  template = file("${path.module}/bootstrap.sh")

  vars = {
    cluster_name    = var.cluster_name
    fleet_name      = local.fleet_name
    pool_size       = var.node_pool_size
    pool_kind       = var.node_pool_kind
    sector_label    = var.sector_label
    lifecycle_label = local.lifecycle_label
    node_taints     = var.node_taints
  }
}
