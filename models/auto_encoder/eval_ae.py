import pandas as pd
from tensorflow import keras
from joblib import load
import numpy as np

# Load
ae = keras.models.load_model('ae_model.h5')
scaler = load('ae_scaler.joblib')
df = pd.read_csv('../../user_features.csv')
Xs = scaler.transform(df[['transaction_count','avg_amount']].values)

# Reconstruct & compute error
recon = ae.predict(Xs)
mse = np.mean((Xs - recon)**2, axis=1)
df['recon_error'] = mse
threshold = df['recon_error'].quantile(0.95)
df['ae_is_fraud'] = df['recon_error'] > threshold

print(df.sort_values('recon_error', ascending=False).head())
