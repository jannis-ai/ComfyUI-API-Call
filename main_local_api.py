import json
import urllib.request
import urllib.parse
import os
import time

# 1. COMPLETELY WIPE PROXY ENV VARIABLES TO PREVENT CONNECTION DROPS
for env_var in ['http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
    os.environ.pop(env_var, None)
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

COMFY_SERVER_URL = "http://127.0.0.1:8188"
WORKFLOW_FILE = "image_z_image_turbo.json"
OUTPUT_NODE_ID = "9"

def queue_workflow(workflow_data):
    """Sends the workflow JSON payload to ComfyUI."""
    payload = {"prompt": workflow_data}
    data = json.dumps(payload).encode('utf-8')
    
    # Explicitly tell urllib not to use any system proxies
    proxy_support = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_support)
    
    req = urllib.request.Request(
        f"{COMFY_SERVER_URL}/prompt", 
        data=data, 
        headers={'Content-Type': 'application/json'}
    )
    
    print("Queuing workflow remotely...")
    with opener.open(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result['prompt_id']

def wait_for_completion(prompt_id):
    """Polls the server history until execution finishes."""
    print("Waiting for generation to finish...")
    proxy_support = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_support)
    
    while True:
        try:
            with opener.open(f"{COMFY_SERVER_URL}/history/{prompt_id}") as response:
                history = json.loads(response.read().decode('utf-8'))
                if prompt_id in history:
                    return history[prompt_id]
        except Exception as e:
            pass
        time.sleep(1)

def download_output_images(history_entry, node_id):
    """Downloads the generated files from history."""
    node_output = history_entry.get('outputs', {}).get(node_id, {})
    if 'images' not in node_output:
        print(f"No images found for Node {node_id}. Making sure it saved properly.")
        return

    print(f"Retrieving outputs from Node {node_id}...")
    for idx, img_info in enumerate(node_output['images']):
        filename = img_info['filename']
        subfolder = img_info.get('subfolder', '')
        img_type = img_info.get('type', 'output')
        
        params = urllib.parse.urlencode({'filename': filename, 'subfolder': subfolder, 'type': img_type})
        view_url = f"{COMFY_SERVER_URL}/view?{params}"
        save_name = f"output_image_{idx}.png" if len(node_output['images']) > 1 else "output_image.png"
        
        print(f"Downloading: {save_name}...")
        urllib.request.urlretrieve(view_url, save_name)
        print("Image saved successfully!")

def run_local_api():
    if not os.path.exists(WORKFLOW_FILE):
        print(f"Error: {WORKFLOW_FILE} not found.")
        return

    print(f"Loading workflow: {WORKFLOW_FILE}...")
    with open(WORKFLOW_FILE, 'r') as f:
        workflow_data = json.load(f)

    # 2. DYNAMICALLY REWRITE NODE 62 TO SAVE TO DISK
    # Converts 'ETN_SendImageWebSocket' into a native 'SaveImage' node structural format
    # if OUTPUT_NODE_ID in workflow_data:
    #     print(f"Converting Node {OUTPUT_NODE_ID} to a standard disk SaveImage node...")
    #     workflow_data[OUTPUT_NODE_ID] = {
    #         "inputs": {
    #             "filename_prefix": "ComfyUI_API",
    #             "images": workflow_data[OUTPUT_NODE_ID]["inputs"]["images"]
    #         },
    #         "class_type": "SaveImage"
    #     }

    # 3. BONUS: How to change your text prompt dynamically in Python
    # Targets Node "57:27" (CLIPTextEncode)
    # workflow_data["57:27"]["inputs"]["text"] = "a cybernetic cat sitting on a neon rooftop"

    try:
        prompt_id = queue_workflow(workflow_data)
        history_entry = wait_for_completion(prompt_id)
        download_output_images(history_entry, OUTPUT_NODE_ID)
    except Exception as e:
        print(f"\nAn error occurred while communicating with ComfyUI: {e}")

if __name__ == "__main__":
    run_local_api()
