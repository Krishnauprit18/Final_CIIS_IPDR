variable "ciis_secret_arns" {
  description = "Secrets Manager ARNs the CIIS application may read"
  type        = list(string)
  default     = []
}
