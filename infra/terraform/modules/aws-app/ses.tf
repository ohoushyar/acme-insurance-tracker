locals {
  ses_enabled    = var.ses_from_address != ""
  ses_from_parts = local.ses_enabled ? split("@", var.ses_from_address) : []
  ses_domain     = length(local.ses_from_parts) == 2 ? local.ses_from_parts[1] : ""
}

resource "aws_sesv2_email_identity" "from" {
  count          = local.ses_enabled ? 1 : 0
  email_identity = local.ses_domain

  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }
}

data "aws_iam_policy_document" "app_ses" {
  count = local.ses_enabled ? 1 : 0
  statement {
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
    ]
    resources = [
      aws_sesv2_email_identity.from[0].arn,
    ]
  }
}

resource "aws_iam_role_policy" "app_ses" {
  count  = local.ses_enabled ? 1 : 0
  name   = "ses-send"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app_ses[0].json
}

resource "aws_route53_record" "ses_dkim" {
  count   = local.ses_enabled && var.ses_hosted_zone_id != "" ? 3 : 0
  zone_id = var.ses_hosted_zone_id
  name = format(
    "%s._domainkey.%s",
    aws_sesv2_email_identity.from[0].dkim_signing_attributes[0].tokens[count.index],
    local.ses_domain,
  )
  type = "CNAME"
  ttl  = 600
  records = [
    format(
      "%s.dkim.amazonses.com",
      aws_sesv2_email_identity.from[0].dkim_signing_attributes[0].tokens[count.index],
    ),
  ]
}
