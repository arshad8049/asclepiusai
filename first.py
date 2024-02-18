import firebase_admin
from firebase_admin import credentials, firestore
import firebase_admin.storage as firebase_storage
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import re
import os
import datetime


# Initialize Firebase
cred = credentials.Certificate("app.json")
firebase_admin.initialize_app(cred, {'storageBucket': 'klasp-d241f.appspot.com'})
db = firestore.client()

# Uploads a file to Google Cloud Storage, makes it public, and returns the public URL
# def upload_blob(source_file_name, destination_blob_name):
#     bucket = firebase_storage.bucket()
#     blob = bucket.blob(destination_blob_name)
#     blob.upload_from_filename(source_file_name, content_type='image/jpeg')
#     blob.make_public()

#     # To avoid caching, append a unique query parameter to the URL
#     unique_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
#     public_url = f"{blob.public_url}?v={unique_id}"
#     print(f"Public URL: {public_url}")
#     return public_url


def upload_blob(source_file_name, destination_blob_name):
    bucket = firebase_storage.bucket()
    # Update the content type for PNG
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name, content_type='image/png')
    
    # Get the current timestamp
    current_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Since the destination_blob_name is the same, the URL remains unchanged
    public_url = blob.public_url
    print(f"Public URL: {public_url}")
    return public_url


# Saves the image URL to Firestore
def save_image_url_to_firestore(user_id, image_url):
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()  # Attempt to retrieve the document
    if not doc.exists:  # If the document does not exist
        user_ref.set({'image_url': image_url})  # Create the document with the image_url
        print(f"Document created and image URL saved to Firestore for user: {user_id}")
    else:
        user_ref.update({'image_url': image_url})  # If the document exists, update it
        print(f"Image URL updated in Firestore for user: {user_id}")


# Extracts text from the provided PDF
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

# Parses the extracted text and returns a list of medication data
def parse_prescription_data_adjusted(text):
    data = []
    med_pattern = r'●\nMedication Name: (.*?)\n●\nDosage: (.*?)\n(?:●\nSuggested Time: (\d+:\d+ [AP]M)\n)?(?:●\nNoon Suggested Time: (\d+:\d+ [AP]M)\n)?(?:●\nEvening Suggested Time: (\d+:\d+ [AP]M)\n)?'
    matches = re.finditer(med_pattern, text, re.DOTALL)
    for match in matches:
        medication = match.group(1).strip()
        dosage = match.group(2).strip()
        times = [time for time in match.groups()[2:] if time and not time.startswith('●')]
        times_str = ', '.join(times)
        data.append({"Medication": medication, "Dosage": dosage, "Suggested Times": times_str})
    return data

# Creates an image of the table with the parsed data
def create_table_image(data):
    image_width = 700
    row_height = 60
    header_height = 50
    image_height = header_height + row_height * len(data)
    image = Image.new('RGB', (image_width, image_height), "white")
    d = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
    header_color = (0, 150, 136)
    row_colors = [(239, 154, 154), (129, 212, 250), (165, 214, 167)]
    
    # Draw the header
    d.rectangle([0, 0, image_width, header_height], fill=header_color)
    headers = ["Medication", "Dosage", "Suggested Times"]
    for i, header in enumerate(headers):
        d.text((10 + i * (image_width // len(headers)), 15), header, fill="white", font=font)
    
    # Draw the rows
    for i, entry in enumerate(data):
        row_color = row_colors[i % len(row_colors)]
        row_y = header_height + i * row_height
        d.rectangle([0, row_y, image_width, row_y + row_height], fill=row_color)
        d.text((10, row_y + 10), entry["Medication"], fill="black", font=font)
        d.text((image_width // 3, row_y + 10), entry["Dosage"], fill="black", font=font)
        d.text((2 * (image_width // 3), row_y + 10), entry["Suggested Times"], fill="black", font=font)
    
    return image

# Function to process the prescription PDF and create the table image
def process_prescription(pdf_path, user_id):
    text = extract_text_from_pdf(pdf_path)
    data = parse_prescription_data_adjusted(text)
    image = create_table_image(data)
    
    # Change the file extension and format to PNG
    output_path = "temp_prescription_table.png"
    
    # Save the image in PNG format
    image.save(output_path, format='PNG')
    
    # Update the destination blob name for PNG format
    destination_blob_name = f"prescriptions/{user_id}/prescription_table.png"
    
    image_url = upload_blob(output_path, destination_blob_name)
    
    # Optionally, update Firestore with the new image URL
    save_image_url_to_firestore(user_id, image_url)
    
    os.remove(output_path)  # Clean up the local file system
    
    print(f"Image updated and uploaded. Public URL: {image_url}")


def generate_signed_url(bucket_name, blob_name):
    """Generates a signed URL for a GCS object."""
    storage_client = google_cloud_storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        version="v4",
        # This URL is valid for 15 minutes
        expiration=datetime.timedelta(minutes=0.10),
        # Allow GET requests using this URL.
        method="GET",
    )

    return url


# Example usage
user_id = 'tuU8peVlEygmeJm5ZdKjk6X0XTQ2'
pdf_path = r"./presdoc3.pdf"  # Adjust path as necessary
process_prescription(pdf_path, user_id)
