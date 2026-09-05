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
  value = aws_cloudfront_distribution.this.id
}

output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.this.domain_name}"
}

output "ses_domain" {
  value = local.ses_domain
}

output "ses_dkim_tokens" {
  value = try(aws_sesv2_email_identity.from[0].dkim_signing_attributes[0].tokens, [])
}

output "alb_hostname" {
  value = local.alb_hostname
}
