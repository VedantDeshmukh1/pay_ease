import os
import streamlit as st
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import pandas as pd
import json

# Load environment variables
load_dotenv()

# Configure Google Generative AI
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

def get_gemini_response(image):
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    prompt_template = """
    Analyze the provided bill image and extract the following information:
    1. List each item name and its corresponding price.
    2. Calculate the subtotal of all items.
    3. Identify any tax amount if present.
    4. Identify any tip amount if present.
    5. Calculate the total bill amount.

    Provide the response in the following JSON format:
    {
        "items": [
            {"name": "Item Name", "price": 0.00},
            ...
        ],
        "subtotal": 0.00,
        "tax": 0.00,
        "tip": 0.00,
        "total": 0.00
    }
    """
    
    try:
        response = model.generate_content([prompt_template, image])
        
        # Try to parse the response as JSON
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # If parsing fails, try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError("Unable to extract JSON from the response")
    
    except Exception as e:
        st.error(f"Error processing the image: {str(e)}")
        st.error("Raw response from Gemini:")
        st.code(response.text)
        return None

def main():
    st.set_page_config(page_title="AI Bill Splitter", page_icon="💰")
    
    st.title("💰 AI Bill Splitter")
    st.write("Upload a bill image, verify the extracted information, and split the bill!")

    # Step 1: Enter names of people
    st.header("Step 1: Enter Names")
    names_input = st.text_input("Enter names separated by commas")
    if names_input:
        names = [name.strip() for name in names_input.split(",")]
        st.session_state['names'] = names
        st.success(f"Names added: {', '.join(names)}")

    # Step 2: Upload image and process
    st.header("Step 2: Upload and Process Bill Image")
    uploaded_file = st.file_uploader("Choose an image of the bill", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Bill", use_column_width=True)
        
        if st.button("Analyze Bill"):
            with st.spinner("Analyzing bill..."):
                bill_data = get_gemini_response(image)
            
            st.session_state['original_bill_data'] = bill_data
            st.session_state['edited_bill_data'] = bill_data.copy()
            st.success("Bill processed successfully!")

    # Step 3: Verify and Edit Extracted Information
    if 'edited_bill_data' in st.session_state:
        st.header("Step 3: Verify and Edit Extracted Information")
        
        # Edit items and prices
        st.subheader("Items and Prices")
        for i, item in enumerate(st.session_state['edited_bill_data']['items']):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input(f"Item {i+1} Name", item['name'])
            with col2:
                new_price = st.number_input(f"Item {i+1} Price", value=float(item['price']), step=0.01, format="%.2f")
            st.session_state['edited_bill_data']['items'][i] = {"name": new_name, "price": new_price}
        
        # Edit subtotal, tax, and tip
        st.subheader("Bill Summary")
        st.session_state['edited_bill_data']['subtotal'] = st.number_input("Subtotal", value=float(st.session_state['edited_bill_data']['subtotal']), step=0.01, format="%.2f")
        st.session_state['edited_bill_data']['tax'] = st.number_input("Tax", value=float(st.session_state['edited_bill_data']['tax']), step=0.01, format="%.2f")
        st.session_state['edited_bill_data']['tip'] = st.number_input("Tip", value=float(st.session_state['edited_bill_data']['tip']), step=0.01, format="%.2f")
        
        # Recalculate total
        st.session_state['edited_bill_data']['total'] = (
            st.session_state['edited_bill_data']['subtotal'] +
            st.session_state['edited_bill_data']['tax'] +
            st.session_state['edited_bill_data']['tip']
        )
        st.write(f"Total: ${st.session_state['edited_bill_data']['total']:.2f}")

    # Step 4: Allocate items
    if 'edited_bill_data' in st.session_state and 'names' in st.session_state:
        st.header("Step 4: Allocate Items")
        
        if 'allocations' not in st.session_state:
            st.session_state['allocations'] = {item['name']: [] for item in st.session_state['edited_bill_data']['items']}
        
        for item in st.session_state['edited_bill_data']['items']:
            st.subheader(f"{item['name']} - ${item['price']:.2f}")
            cols = st.columns(len(st.session_state['names']))
            for idx, name in enumerate(st.session_state['names']):
                if cols[idx].checkbox(name, key=f"{item['name']}_{name}"):
                    if name not in st.session_state['allocations'][item['name']]:
                        st.session_state['allocations'][item['name']].append(name)
                else:
                    if name in st.session_state['allocations'][item['name']]:
                        st.session_state['allocations'][item['name']].remove(name)

    # Step 5: Calculate and display results
    if st.button("Calculate Split"):
        if 'allocations' in st.session_state and 'edited_bill_data' in st.session_state:
            st.header("Bill Summary")
            
            # Calculate individual costs
            individual_costs = {name: 0 for name in st.session_state['names']}
            for item in st.session_state['edited_bill_data']['items']:
                allocated_to = st.session_state['allocations'][item['name']]
                if allocated_to:
                    cost_per_person = item['price'] / len(allocated_to)
                    for name in allocated_to:
                        individual_costs[name] += cost_per_person
            
            # Display results
            results_df = pd.DataFrame(list(individual_costs.items()), columns=['Name', 'Amount'])
            results_df['Amount'] = results_df['Amount'].round(2)
            st.table(results_df)
            
            # Display bill details
            st.subheader("Bill Details")
            st.write(f"Subtotal: ${st.session_state['edited_bill_data']['subtotal']:.2f}")
            st.write(f"Tax: ${st.session_state['edited_bill_data']['tax']:.2f}")
            st.write(f"Tip: ${st.session_state['edited_bill_data']['tip']:.2f}")
            st.write(f"Total: ${st.session_state['edited_bill_data']['total']:.2f}")
            
            # Calculate and distribute tax and tip
            tax_and_tip = st.session_state['edited_bill_data']['tax'] + st.session_state['edited_bill_data']['tip']
            tax_and_tip_per_person = tax_and_tip / len(st.session_state['names'])
            
            final_costs = {name: cost + tax_and_tip_per_person for name, cost in individual_costs.items()}
            final_df = pd.DataFrame(list(final_costs.items()), columns=['Name', 'Final Amount'])
            final_df['Final Amount'] = final_df['Final Amount'].round(2)
            
            st.subheader("Final Bill Split (including tax and tip)")
            st.table(final_df)

if __name__ == "__main__":
    main()
