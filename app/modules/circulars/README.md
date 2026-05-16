# app/modules/circulars/

This module is **training-data only**.

The router is intentionally **not registered** in `app/main.py`.
Do **not** register it — the circulars endpoint is not part of the production API.

The ML classifier in `app/modules/ml/` uses the circulars data from this module
to train and run the circular category classifier. Deleting this module would
break the training pipeline.
