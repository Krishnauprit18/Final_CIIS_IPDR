resource "aws_s3_bucket" "raw" {
  bucket = "ciis-raw-files"
}

resource "aws_s3_bucket" "results" {
  bucket = "ciis-results"
}

output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "results_bucket" {
  value = aws_s3_bucket.results.bucket
}
