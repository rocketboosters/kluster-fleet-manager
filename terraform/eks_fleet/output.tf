output "template_version" {
  value = aws_launch_template.fleet.latest_version
}

output "template_id" {
  value = aws_launch_template.fleet.id
}

output "fleet_id" {
  value = aws_ec2_fleet.fleet.id
}
