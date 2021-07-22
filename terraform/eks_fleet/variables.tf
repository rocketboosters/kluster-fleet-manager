variable "tags" {
  type = map(string)
  default = {}
  description = "Additional tags to apply to fleet resources."
}

variable "cluster_name" {
  type = string
  description = "Name of the EKS cluster that will utilize this fleet."
}

variable "ami" {
  # Find values at:
  # https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html
  type = string
  description = "AMI that will be used by the nodes in the fleet. Find values at: https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html"
}

variable "spot" {
  type = bool
  description = "Whether to use spot nodes for this fleet."
}

variable "sector_label" {
  type = string
  description = "Name of the node pool sector this fleet will reside."
}

variable "node_pool_size" {
  type = string
  description = "T-Shirt size specifying the size of nodes to use in this fleet, e.g. 'xsmall', 'medium', 'large', ..."
  validation {
    condition = contains(
      ["xsmall", "small", "medium", "large", "xlarge"],
      var.node_pool_size
    )
    error_message = "Must be one of: xsmall, small, medium, large, or xlarge."
  }
}

variable "node_pool_kind" {
  type = string
  description = "Primary resource allocation for the nodes to use in the fleet, either memory or cpu optimized. General purpose nodes are used in both as fallback options."
  validation {
    condition = contains(["memory", "cpu"], var.node_pool_kind)
    error_message = "Must be one of memory or cpu."
  }
}

variable "private_subnet_ids" {
  type = map(string)
  description = "A map where the keys are AZs and the values are the private Subnet IDs in which the fleet nodes are allowed to launch."
}


variable "ebs_size" {
  type = number
  default = 20
  description = "Gigabytes of disk used for the images."
}

variable "ssh_key_name" {
  type = string
  description = "Name of the AWS SSH key to associate with the instances."
}

variable "instance_profile_name" {
  type = string
  description = "Name of the instance profile attached to these nodes."
}

variable "security_group_id" {
  type = string
  description = "ID for the VPC security group that nodes in this fleet will use for networking."
}

variable "node_taints" {
  type    = string
  default = ""
  description = "String list of taints to apply to the nodes at startup. Used for additional placement customization if needed."
}

variable "initial_node_count" {
  type = number
  default = 0
  description = "Initial number of nodes to launch the fleet with."
}
