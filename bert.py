# -*- coding: utf-8 -*-
"""BERT.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1YXWSsyZkQKj-jWBQ6nZLpqmMrKrV0Db8
"""

!pip install accelerate
!pip install transformers
!pip install torch

import pandas as pd
import re
import torch
from transformers import BertTokenizer, BertForSequenceClassification
from transformers import Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from torch.utils.data import Dataset, DataLoader
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaTokenizer, RobertaForSequenceClassification, AdamW
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# Sample data

!wget https://raw.githubusercontent.com/tizfa/tweepfake_deepfake_text_detection/master/data/splits/train.csv -O train.csv
!wget https://raw.githubusercontent.com/tizfa/tweepfake_deepfake_text_detection/master/data/splits/validation.csv -O validation.csv
!wget https://raw.githubusercontent.com/tizfa/tweepfake_deepfake_text_detection/master/data/splits/test.csv -O test.csv

train_df = pd.read_csv('train.csv', delimiter=';')
test_df = pd.read_csv('test.csv', delimiter=';')
val_df = pd.read_csv('validation.csv', delimiter=';')

print(train_df.head())
print(test_df.head())
print(val_df.head())

train_df.shape

test_df.shape

val_df.shape

train_df.head()

# Drop 'class_type' and 'screen_name' columns from test_df
test_df = test_df.drop(columns=['class_type', 'screen_name'])

# Drop 'class_type' and 'screen_name' columns from train_df and val_df similarly
train_df = train_df.drop(columns=['class_type', 'screen_name'])
val_df = val_df.drop(columns=['class_type', 'screen_name'])

test_df.isnull().sum()

val_df.isnull().sum()

test_df.isnull().sum()

# Clean the text
def clean_text(text):
    text = re.sub(r"http\S+", "", text)  # Remove URLs
    text = re.sub(r"@\w+", "", text)  # Remove mentions
    text = re.sub(r"[^a-zA-Z\s]", "", text)  # Remove special characters
    text = text.lower()  # Convert to lowercase
    text = re.sub(r"\s+", " ", text).strip()  # Remove extra whitespace
    return text

val_df['cleaned_text'] = val_df['text'].apply(clean_text)

val_df

test_df['cleaned_text'] = test_df['text'].apply(clean_text)

test_df

train_df['cleaned_text'] = train_df['text'].apply(clean_text)

train_df

# Encode labels
label_mapping = {'human': 0, 'bot': 1,}
val_df['label'] = val_df['account.type'].map(label_mapping)

val_df

# Encode labels
label_mapping = {'human': 0, 'bot': 1,}
train_df['label'] = train_df['account.type'].map(label_mapping)

# Encode labels
label_mapping = {'human': 0, 'bot': 1,}
test_df['label'] = test_df['account.type'].map(label_mapping)

test_df

test_df

# Drop 'class_type' and 'screen_name' columns from test_df
test_df = test_df.drop(columns=['account.type', 'text'])

# Drop 'class_type' and 'screen_name' columns from train_df and val_df similarly
train_df = train_df.drop(columns=['account.type', 'text'])
val_df = val_df.drop(columns=['account.type', 'text'])

train_df

y_train = train_df["label"]
y_val = val_df["label"]
y_test = test_df["label"]

y_train

class TweetDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts.iloc[idx]
        label = self.labels.iloc[idx]
        encoding = self.tokenizer(text, truncation=True, padding='max_length', max_length=self.max_length, return_tensors='pt')
        item = {key: val.squeeze(0) for key, val in encoding.items()}
        item['labels'] = torch.tensor(label)
        return item

# Experment 2

from transformers import BertTokenizer, BertForSequenceClassification, AdamW, get_linear_schedule_with_warmup
from torch.utils.data import DataLoader, Dataset
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# Initialize the model
model = BertForSequenceClassification.from_pretrained('bert-base-uncased')

# Tokenizer and datasets
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

train_dataset = TweetDataset(train_df['cleaned_text'], train_df['label'], tokenizer, max_length=128)
val_dataset = TweetDataset(val_df['cleaned_text'], val_df['label'], tokenizer, max_length=128)
test_dataset = TweetDataset(test_df['cleaned_text'], test_df['label'], tokenizer, max_length=128)

# Create DataLoaders
train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)

# Training configurations
num_epochs = 7
batch_size = 32
learning_rate = 2e-5

# Use GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# Define optimizer, loss function, and scheduler
optimizer = AdamW(model.parameters(), lr=learning_rate)
total_steps = len(train_dataset) // batch_size * num_epochs
scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=total_steps)
loss_fn = torch.nn.CrossEntropyLoss()

# Training loop with early stopping and gradient clipping
best_val_accuracy = 0.0
patience = 3
no_improvement_epochs = 0
train_losses = []
val_losses = []

for epoch in range(num_epochs):
    model.train()
    total_loss = 0
    correct = 0
    total_samples = 0

    train_loader = tqdm(DataLoader(train_dataset, batch_size=batch_size, shuffle=True), desc=f"Epoch {epoch+1}/{num_epochs}")

    for batch in train_loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        optimizer.zero_grad()
        outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
        loss = outputs.loss
        total_loss += loss.item()

        logits = outputs.logits
        predictions = torch.argmax(logits, dim=1)
        correct += (predictions == labels).sum().item()
        total_samples += labels.size(0)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        train_loader.set_postfix(loss=total_loss, accuracy=correct / total_samples)

    train_accuracy = correct / total_samples
    train_losses.append(total_loss)

    # Validation step
    model.eval()
    val_correct = 0
    val_loss = 0
    val_total_samples = 0

    with torch.no_grad():
        for batch in DataLoader(val_dataset, batch_size=batch_size):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            predictions = torch.argmax(logits, dim=1)
            val_loss += loss_fn(logits, labels).item()
            val_correct += (predictions == labels).sum().item()
            val_total_samples += labels.size(0)

    val_accuracy = val_correct / val_total_samples
    val_losses.append(val_loss)
    print(f"Epoch {epoch+1}/{num_epochs}, Train Loss: {total_loss}, Train Accuracy: {train_accuracy}, Val Accuracy: {val_accuracy}")

    if val_accuracy > best_val_accuracy:
        best_val_accuracy = val_accuracy
        no_improvement_epochs = 0
        torch.save(model.state_dict(), 'best_model.pt')
    else:
        no_improvement_epochs += 1
        if no_improvement_epochs >= patience:
            print("Early stopping triggered")
            break

# Load the best model
model.load_state_dict(torch.load('best_model.pt'))

# Test the trained model on the test dataset
test_predictions = []
test_true_labels = []

with torch.no_grad():
    for batch in tqdm(DataLoader(test_dataset, batch_size=batch_size), desc="Testing"):
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        outputs = model(input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        predictions = torch.argmax(logits, dim=1)
        test_predictions.extend(predictions.cpu().numpy())
        test_true_labels.extend(labels.cpu().numpy())

test_accuracy = accuracy_score(test_true_labels, test_predictions)
test_f1 = f1_score(test_true_labels, test_predictions, average='weighted')
test_precision = precision_score(test_true_labels, test_predictions, average='weighted')
test_recall = recall_score(test_true_labels, test_predictions, average='weighted')

print(f"Test Accuracy: {test_accuracy}")
print(f"Test F1 Score: {test_f1}")
print(f"Test Precision: {test_precision}")
print(f"Test Recall: {test_recall}")

# Plotting training and validation loss
plt.figure(figsize=(10, 5))
plt.plot(range(1, len(train_losses) + 1), train_losses, label='Training Loss')
plt.plot(range(1, len(val_losses) + 1), val_losses, label='Validation Loss')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.title('Training and Validation Loss')
plt.legend()
plt.show()

# Plotting confusion matrix
cm = confusion_matrix(test_true_labels, test_predictions)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='viridis', xticklabels=['human', 'bot'], yticklabels=['human', 'bot'])
plt.xlabel('Predicted label')
plt.ylabel('True label')
plt.title('Confusion Matrix')
plt.show()

# Experment 3

from transformers import BertModel, BertPreTrainedModel, BertTokenizer
from torch import nn
from transformers import get_linear_schedule_with_warmup
from tqdm import tqdm
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns


class BertForSequenceClassificationWithDropout(BertPreTrainedModel):
    def __init__(self, config, dropout_prob=0.3):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(dropout_prob)
        self.classifier = nn.Linear(config.hidden_size, config.num_labels)
        self.init_weights()

    def forward(self, input_ids, attention_mask=None, token_type_ids=None, labels=None):
        outputs = self.bert(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        pooled_output = outputs[1]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)

        loss = None
        if labels is not None:
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(logits.view(-1, self.num_labels), labels.view(-1))

        return logits, loss

# Initialize the model with dropout
model = BertForSequenceClassificationWithDropout.from_pretrained('bert-base-uncased')

# Tokenizer and datasets
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

train_dataset = TweetDataset(train_df['cleaned_text'], train_df['label'], tokenizer, max_length=128)
val_dataset = TweetDataset(val_df['cleaned_text'], val_df['label'], tokenizer, max_length=128)
test_dataset = TweetDataset(test_df['cleaned_text'], test_df['label'], tokenizer, max_length=128)

# Create DataLoaders
train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)

# Training configurations
num_epochs = 7
batch_size = 32
learning_rate = 1e-5

# Use GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# Define optimizer, loss function, and scheduler
optimizer = AdamW(model.parameters(), lr=learning_rate)
total_steps = len(train_dataset) // batch_size * num_epochs
scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=total_steps)
loss_fn = torch.nn.CrossEntropyLoss()

# Training loop with early stopping and gradient clipping
best_val_accuracy = 0.0
patience = 3
no_improvement_epochs = 0
train_losses = []
val_losses = []

for epoch in range(num_epochs):
    model.train()
    total_loss = 0
    correct = 0
    total_samples = 0

    train_loader = tqdm(DataLoader(train_dataset, batch_size=batch_size, shuffle=True), desc=f"Epoch {epoch+1}/{num_epochs}")

    for batch in train_loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        optimizer.zero_grad()
        logits, loss = model(input_ids, attention_mask=attention_mask, labels=labels)
        total_loss += loss.item()

        predictions = torch.argmax(logits, dim=1)
        correct += (predictions == labels).sum().item()
        total_samples += labels.size(0)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        train_loader.set_postfix(loss=total_loss, accuracy=correct / total_samples)

    train_accuracy = correct / total_samples
    train_losses.append(total_loss)

    # Validation step
    model.eval()
    val_correct = 0
    val_loss = 0
    val_total_samples = 0

    with torch.no_grad():
        for batch in DataLoader(val_dataset, batch_size=batch_size):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            logits, _ = model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = loss_fn(logits, labels)
            val_loss += loss.item()
            predictions = torch.argmax(logits, dim=1)
            val_correct += (predictions == labels).sum().item()
            val_total_samples += labels.size(0)

    val_accuracy = val_correct / val_total_samples
    val_losses.append(val_loss)
    print(f"Epoch {epoch+1}/{num_epochs}, Train Loss: {total_loss}, Train Accuracy: {train_accuracy}, Val Accuracy: {val_accuracy}")

    if val_accuracy > best_val_accuracy:
        best_val_accuracy = val_accuracy
        no_improvement_epochs = 0
        torch.save(model.state_dict(), 'best_model.pt')
    else:
        no_improvement_epochs += 1
        if no_improvement_epochs >= patience:
            print("Early stopping triggered")
            break

# Load the best model
model.load_state_dict(torch.load('best_model.pt'))

# Test the trained model on the test dataset
test_predictions = []
test_true_labels = []

with torch.no_grad():
    for batch in tqdm(DataLoader(test_dataset, batch_size=batch_size), desc="Testing"):
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        logits, _ = model(input_ids, attention_mask=attention_mask, labels=labels)
        predictions = torch.argmax(logits, dim=1)
        test_predictions.extend(predictions.cpu().numpy())
        test_true_labels.extend(labels.cpu().numpy())

test_accuracy = accuracy_score(test_true_labels, test_predictions)
test_f1 = f1_score(test_true_labels, test_predictions, average='weighted')
test_precision = precision_score(test_true_labels, test_predictions, average='weighted')
test_recall = recall_score(test_true_labels, test_predictions, average='weighted')

print(f"Test Accuracy: {test_accuracy}")
print(f"Test F1 Score: {test_f1}")
print(f"Test Precision: {test_precision}")
print(f"Test Recall: {test_recall}")

# Plotting training and validation loss
plt.figure(figsize=(10, 5))
plt.plot(range(1, len(train_losses) + 1), train_losses, label='Training Loss')
plt.plot(range(1, len(val_losses) + 1), val_losses, label='Validation Loss')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.title('Training and Validation Loss')
plt.legend()
plt.show()

# Plotting confusion matrix
cm = confusion_matrix(test_true_labels, test_predictions)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='viridis', xticklabels=['human', 'bot'], yticklabels=['human', 'bot'])
plt.xlabel('Predicted label')
plt.ylabel('True label')
plt.title('Confusion Matrix')
plt.show()

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

# Test the trained model on the test dataset
test_predictions = []
test_true_labels = []

with torch.no_grad():
    for batch in tqdm(DataLoader(test_dataset, batch_size=batch_size), desc="Testing"):
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        logits, _ = model(input_ids, attention_mask=attention_mask, labels=labels)
        predictions = torch.argmax(logits, dim=1)
        test_predictions.extend(predictions.cpu().numpy())
        test_true_labels.extend(labels.cpu().numpy())

test_accuracy = accuracy_score(test_true_labels, test_predictions)
test_f1 = f1_score(test_true_labels, test_predictions, average='weighted')
test_precision = precision_score(test_true_labels, test_predictions, average='weighted')
test_recall = recall_score(test_true_labels, test_predictions, average='weighted')

print(f"Test Accuracy: {test_accuracy}")
print(f"Test F1 Score: {test_f1}")
print(f"Test Precision: {test_precision}")
print(f"Test Recall: {test_recall}")

# Plotting training and validation loss
plt.figure(figsize=(10, 5))
plt.plot(range(1, len(train_losses) + 1), train_losses, label='Training Loss')
plt.plot(range(1, len(val_losses) + 1), val_losses, label='Validation Loss')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.title('Training and Validation Loss')
plt.legend()
plt.show()

# Plotting confusion matrix
cm = confusion_matrix(test_true_labels, test_predictions)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='viridis', xticklabels=['human', 'bot'], yticklabels=['human', 'bot'])
plt.xlabel('Predicted label')
plt.ylabel('True label')
plt.title('Confusion Matrix')
plt.show()