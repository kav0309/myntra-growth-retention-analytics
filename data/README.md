# Source Data Setup

Raw data is **not committed** to this repository.

Download the **E-commerce App Transactional Dataset** by Aditya Bagus Pratama from Kaggle:

`https://www.kaggle.com/datasets/bytadit/transactional-ecommerce`

Place the source files here:

```text
data/raw/
├── customer.csv
├── product.csv
├── click_stream.csv
└── transactions.csv
```

Then run:

```bash
python analysis/prepare_clickstream.py \
  --input data/raw/click_stream.csv \
  --output data/raw/clickstream_sessions.csv

python analysis/build_metrics.py \
  --data-dir data/raw \
  --output-dir analysis/outputs
```

The public repository should contain only the aggregate outputs under `analysis/outputs/`, not the raw customer-level dataset.
