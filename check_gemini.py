import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

api_key = os.getenv("GEMINI_KEY")

if not api_key:
    print("❌ GEMINI_KEY not found in .env file!")
    exit(1)

print("🔍 Testing Gemini Models...\n")

# List of models to test
models_to_test = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-2.0-flash-exp",
    "gemini-2.5-flash",
    "gemini-2.5-flash-latest",
    "gemini-pro",
]

working_models = []

for model_name in models_to_test:
    try:
        print(f"Testing: {model_name}...", end=" ")
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.1,
            google_api_key=api_key
        )
        
        # Test with a simple prompt
        response = llm.invoke("Say 'OK' if you can read this.")
        
        print(f"✅ WORKS! Response: {response.content[:50]}")
        working_models.append(model_name)
        
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            print(f"❌ Not found (404)")
        elif "permission" in error_msg.lower():
            print(f"❌ Permission denied")
        else:
            print(f"❌ Error: {error_msg[:100]}")

print("\n" + "="*60)
print(f"\n✅ Working Models ({len(working_models)}):")
for model in working_models:
    print(f"   • {model}")

if working_models:
    print(f"\n💡 Recommended: Use '{working_models[0]}' in your app")
else:
    print("\n⚠️  No working models found. Check your API key!")
