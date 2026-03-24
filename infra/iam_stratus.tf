# -----------------------------------------------------------------------------
# IAM user for Stratus Red Team (attack simulation)
# -----------------------------------------------------------------------------
# Credentials are exposed via terraform output and build.sh → .env.stratus.
#
# Default path (recommended for most Stratus techniques):
#   Attach AWS managed PowerUserAccess + IAMFullAccess. PowerUser covers most
#   services; IAMFullAccess is needed for IAM-focused abuse techniques.
#
# Optional least-privilege path:
#   Comment out the two aws_iam_user_policy_attachment resources below, then
#   uncomment and edit the stratus_scoped policy at the bottom. The managed
#   policies must be removed first—otherwise they still grant broad access and
#   your custom policy does not reduce the effective permission set.
#
# Optional custom policy (advanced):
#   Steps: (1) Remove or comment out stratus_power_user and stratus_iam_full.
#          (2) Uncomment stratus_scoped.
#          (3) Replace the example Action list with APIs required by the Stratus
#              techniques you run (see Stratus documentation per technique).
# -----------------------------------------------------------------------------

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
