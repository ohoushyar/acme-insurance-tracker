output "namespace" {
  value = local.namespace
}

output "frontend_bucket" {
  value = aws_s3_bucket.web.bucket
}

output "docs_bucket" {
  value = aws_s3_bucket.docs.bucket
}

output "cloudfront_distribution_id" {
  value = try(aws_cloudfront_distribution.this[0].id, "")
}

output "cloudfront_url" {
  value = try("https://${aws_cloudfront_distribution.this[0].domain_name}", "")
}

output "alb_hostname" {
  value = local.alb_hostname
}
