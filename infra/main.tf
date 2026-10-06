terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.region }
variable "region" { type = string }
variable "bucket_name" { type = string }
resource "aws_s3_bucket" "lake" {
  bucket = var.bucket_name
  force_destroy = false
  tags = { Project = "pyspark-dbt-scd2" }
}
resource "aws_s3_bucket_public_access_block" "lake" {
  bucket = aws_s3_bucket.lake.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_policy" "tls" {
  bucket = aws_s3_bucket.lake.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid = "DenyInsecureTransport", Effect = "Deny", Principal = "*",
    Action = "s3:*", Resource = [aws_s3_bucket.lake.arn, "${aws_s3_bucket.lake.arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
output "bucket_name" { value = aws_s3_bucket.lake.id }
