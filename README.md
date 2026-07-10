# Photoshop Logo Placement Automation

An end-to-end computer vision pipeline for automatically detecting garment logo positions and generating Photoshop-ready mockups.

The system combines a custom-trained **YOLOv11 Oriented Bounding Box (OBB)** model with a Photoshop automation pipeline to accurately place logos on garments, caps, bags, towels, and other products with minimal manual intervention.

## Overview

Traditional mockup generation requires manually positioning logos for every garment image, making it slow, repetitive, and difficult to scale.

This project automates that workflow by:

* Detecting predefined decoration locations using a custom YOLOv11 OBB model.
* Estimating placement coordinates and rotation angles.
* Processing batch orders from Excel.
* Automatically generating Photoshop compositions for thousands of product images.

The complete pipeline was built to support high-volume production while maintaining consistent logo placement accuracy.

## Features

* Custom YOLOv11 OBB model for logo placement detection.
* Detection of multiple garment categories including garments, caps, bags, and towels.
* Rotation-aware placement using oriented bounding boxes.
* Automated Photoshop batch generation.
* Excel-driven batch processing.
* Image preprocessing before inference.
* Fallback heuristics when detections are unavailable.
* Detailed batch logging and reporting.
* GUI tools for annotation and workflow management.

## Dataset

The detection model was trained using approximately **2,500 manually annotated images** covering multiple product categories and decoration positions.

Annotations were created using a custom-built OBB annotation tool designed specifically for this project.

## OBB Annotation Tool

To efficiently build the training dataset, a dedicated annotation application was developed.

Features include:

* Interactive oriented bounding box annotation.
* Multiple predefined decoration classes.
* Rotation, resizing, and editing tools.
* Annotation copy/paste between similar products.
* Category-based dataset organization.
* Automatic annotation management.
* Keyboard shortcuts for rapid labeling.

The annotation tool significantly reduced dataset creation time while maintaining annotation consistency across thousands of images.

## Model Training

The detection model is based on **YOLOv11 OBB** and trained using the Ultralytics framework.

Training includes:

* Oriented Bounding Box detection.
* GPU-accelerated training.
* AdamW optimizer.
* Extensive augmentation.
* High-resolution training images.
* Long-running training with early stopping.

The training pipeline is fully configurable for retraining with additional data as the dataset grows.

## Automation Pipeline

The production workflow consists of two major stages:

### 1. Data Preparation

* Read batch information from Excel.
* Validate images and logo assets.
* Resolve product metadata.
* Preprocess images.
* Prepare placement configuration.

### 2. Automated Processing

For each product image:

* Detect decoration locations using the trained YOLOv11 OBB model.
* Extract placement coordinates and rotation.
* Apply fallback logic when required.
* Generate Photoshop batch instructions.
* Produce final mockup-ready outputs.
* Generate processing logs and reports.

The pipeline is designed for large-scale batch execution while providing robust validation, logging, and error recovery throughout the process.

## Tech Stack

* Python
* YOLOv11 OBB
* Ultralytics
* OpenCV
* PyTorch
* Photoshop Automation
* Tkinter
* Pillow

## Project Structure

* **Annotation Tool** — Dataset labeling for OBB detection.
* **Training Pipeline** — YOLOv11 OBB model training.
* **Detection Modules** — Product-specific placement detection.
* **Automation Engine** — Excel-driven batch processing.
* **Photoshop Integration** — Automated mockup generation.
* **Logging & Reporting** — Batch diagnostics and execution reports.

## Results

The completed system automates the majority of the mockup generation workflow, enabling large batches of apparel images to be processed with minimal manual intervention while maintaining consistent logo placement across supported product categories.
