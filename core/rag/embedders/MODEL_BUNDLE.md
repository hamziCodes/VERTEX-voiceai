# Approved local embedding bundle

The production adapter is pinned to `intfloat/multilingual-e5-small`, which
produces 384-dimensional multilingual sentence embeddings compatible with the
`vector(384)` database schema.

The application never downloads a model at runtime. Provision a reviewed model
bundle outside Git and configure its directory as `UCVE_EMBEDDING_MODEL_PATH`.
The directory must contain:

- `model.onnx`
- `tokenizer.json`
- `embedding_model.json`

Example metadata:

```json
{
  "model_id": "intfloat/multilingual-e5-small",
  "version": "pinned-upstream-commit-or-internal-release",
  "dimensions": 384,
  "max_length": 512,
  "query_prefix": "query: ",
  "passage_prefix": "passage: ",
  "pad_id": 1,
  "pad_token": "<pad>"
}
```

Deployment must pin and verify the chosen upstream model revision and artifact
checksums before placing the bundle on a worker. Model files are intentionally
excluded from the Python package and repository because they are large binary
artifacts with separate provenance and license review requirements.
