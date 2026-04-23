import streamlit as st
from PIL import Image, ImageEnhance
from rembg import remove
import io
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import streamlit.components.v1 as components

# --- INITIALIZE MEDIAPIPE FACE DETECTOR ---
base_options = python.BaseOptions(model_asset_path='blaze_face_short_range.tflite')
options = vision.FaceDetectorOptions(base_options=base_options)
face_detector = vision.FaceDetector.create_from_options(options)

st.set_page_config(page_title="AI Passport Studio Pro", layout="wide")

st.title("📸 AI Passport Studio: Pro Edition")
st.markdown("---")

# --- SIDEBAR: CONTROLS ---
st.sidebar.header("🎨 Edit Settings")
mode = st.sidebar.selectbox("Mode", ["Single Photo", "Joint Photo"])
bg_color = st.sidebar.color_picker("Background Color", "#0047AB")

st.sidebar.subheader("✨ Enhancements")
brightness = st.sidebar.slider("Brightness", 0.5, 2.0, 1.0)
contrast = st.sidebar.slider("Contrast", 0.5, 2.0, 1.1)

st.sidebar.header("🖨️ Layout & Print")
total_photos = st.sidebar.number_input("Total Photos", min_value=1, max_value=50, value=12)
layout_style = st.sidebar.radio("Fill Priority", ["By Row", "By Column"])
photos_per_line = st.sidebar.slider("Photos per Row/Column", 1, 8, 7)

# --- FUNCTIONS ---
def auto_crop_face(img):
    w, h = img.size
    img_array = np.array(img.convert("RGB"))
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)
    detection_result = face_detector.detect(mp_image)
    
    if detection_result.detections:
        bbox = detection_result.detections[0].bounding_box
        center_x = bbox.origin_x + bbox.width / 2
        center_y = bbox.origin_y + bbox.height / 2
        
        # Passport ratio calculation
        crop_w = bbox.width * 2.3
        crop_h = crop_w * (4.5 / 3.5)
        
        left = max(0, center_x - crop_w / 2)
        top = max(0, center_y - crop_h / 2.2)
        
        return img.crop((left, top, min(w, left + crop_w), min(h, top + crop_h)))
    return img

def process_image(img, bg_hex):
    # 1. AI Face Crop
    img = auto_crop_face(img)
    # 2. Background Remove
    img_no_bg = remove(img)
    # 3. Apply Background Color
    bg_rgb = tuple(int(bg_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    final_img = Image.new("RGBA", img_no_bg.size, bg_rgb + (255,))
    final_img.paste(img_no_bg, (0, 0), img_no_bg)
    # 4. Filter Enhancements
    final_img = ImageEnhance.Brightness(final_img).enhance(brightness)
    final_img = ImageEnhance.Contrast(final_img).enhance(contrast)
    # Resize to Standard 3.5x4.5 cm (413x531 px at 300 DPI)
    return final_img.convert("RGB").resize((413, 531), Image.Resampling.LANCZOS)

def create_custom_sheet(img, total, line_count, priority):
    a4_w, a4_h = 2480, 3508 # A4 @ 300DPI
    sheet = Image.new("RGB", (a4_w, a4_h), (255, 255, 255))
    x_start, y_start, gap = 100, 100, 45
    photo_w, photo_h = img.size
    curr_x, curr_y = x_start, y_start

    for i in range(total):
        sheet.paste(img, (curr_x, curr_y))
        if priority == "By Row":
            if (i + 1) % line_count == 0:
                curr_x = x_start
                curr_y += photo_h + gap
            else:
                curr_x += photo_w + gap
        else:
            if (i + 1) % line_count == 0:
                curr_y = y_start
                curr_x += photo_w + gap
            else:
                curr_y += photo_h + gap
        if curr_y + photo_h > a4_h or curr_x + photo_w > a4_w:
            break
    return sheet

# --- MAIN UI ---
uploaded = st.file_uploader("Upload Photo", type=["jpg", "png", "jpeg"], accept_multiple_files=(mode == "Joint Photo"))

if uploaded:
    final_photo = None
    try:
        if mode == "Single Photo" and not isinstance(uploaded, list):
            with st.spinner("Processing AI Filters..."):
                final_photo = process_image(Image.open(uploaded), bg_color)
        elif mode == "Joint Photo" and len(uploaded) == 2:
            with st.spinner("Processing Joint Photos..."):
                res1 = process_image(Image.open(uploaded[0]), bg_color)
                res2 = process_image(Image.open(uploaded[1]), bg_color)
                final_photo = Image.new("RGB", (826, 531))
                final_photo.paste(res1, (0, 0))
                final_photo.paste(res2, (413, 0))

        if final_photo:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.subheader("Final Result")
                st.image(final_photo, width=220)
                
                format_choice = st.selectbox("Export Format", ["JPG", "PNG", "PSD"])
                buf = io.BytesIO()
                if format_choice == "JPG":
                    final_photo.save(buf, format="JPEG", quality=95)
                    m_type = "image/jpeg"
                elif format_choice == "PNG":
                    final_photo.save(buf, format="PNG")
                    m_type = "image/png"
                else:
                    final_photo.save(buf, format="PSD")
                    m_type = "application/x-photoshop"
                
                st.download_button(f"Download Single ({format_choice})", buf.getvalue(), f"passport_photo.{format_choice.lower()}", m_type)

            with col2:
                st.subheader("Print Preview (A4)")
                custom_sheet = create_custom_sheet(final_photo, total_photos, photos_per_line, layout_style)
                st.image(custom_sheet, use_column_width=True)
                
                # JavaScript Print
                if st.button("🖨️ Open Print Dialog"):
                    img_buf = io.BytesIO()
                    custom_sheet.save(img_buf, format="PNG")
                    import base64
                    img_str = base64.b64encode(img_buf.getvalue()).decode()
                    components.html(f"""
                        <script>
                        var win = window.open('', '_blank');
                        win.document.write('<html><body style="margin:0;"><img src="data:image/png;base64,{img_str}" style="width:100%;"></body></html>');
                        win.document.close();
                        setTimeout(function(){{ win.print(); }}, 500);
                        </script>
                    """, height=0)

                sheet_buf = io.BytesIO()
                custom_sheet.save(sheet_buf, format="JPEG", quality=100)
                st.download_button("Download A4 Sheet (JPG)", sheet_buf.getvalue(), "a4_print_sheet.jpg", "image/jpeg")
    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Photo upload karein process shuru karne ke liye.")