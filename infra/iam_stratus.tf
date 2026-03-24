# Stratus Red Team user. Keys: terraform output / .env.stratus (build.sh).
#
# Default (below): attach PowerUserAccess + IAMFullAccess so most Stratus techniques work out of the box.
#
# Optional (commented block at bottom): use a custom inline policy with only the API actions you need.
# If you switch to that, remove the two aws_iam_user_policy_attachment resources first — otherwise the
# managed policies would still apply and would override the point of a narrow policy.

resource "aws_iam_user" "stratus" {
  count = var.create_stratus_iam_user ? 1 : 0

  name = "${var.project_name}-stratus"
  path = "/"

  tags = {
    Name      = "${var.project_name}-stratus"
    ManagedBy = "terraform"
    Project   = "aws-soc-lab"
  }
}

resource "aws_iam_access_key" "stratus" {
  count = var.create_stratus_iam_user ? 1 : 0

  user = aws_iam_user.stratus[0].name
}

resource "aws_iam_user_policy_attachment" "stratus_power_user" {
  count = var.create_stratus_iam_user ? 1 : 0

  user       = aws_iam_user.stratus[0].name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_user_policy_attachment" "stratus_iam_full" {
  count = var.create_stratus_iam_user ? 1 : 0

  user       = aws_iam_user.stratus[0].name
  policy_arn = "arn:aws:iam::aws:policy/IAMFullAccess"
}

# Optional custom policy (advanced). Steps: (1) Delete or comment out stratus_power_user and
# stratus_iam_full above. (2) Uncomment stratus_scoped below. (3) Replace the example Action list
# with the permissions your techniques need (Stratus docs list required APIs per technique).
#
# resource "aws_iam_user_policy" "stratus_scoped" {
#   count = var.create_stratus_iam_user ? 1 : 0
#   name  = "${var.project_name}-stratus-scoped"
#   user  = aws_iam_user.stratus[0].name
#
#   policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect   = "Allow"
#         Action   = ["ec2:DescribeInstances", "sts:GetCallerIdentity"]
#         Resource = "*"
#       }
#     ]
#   })
# }
