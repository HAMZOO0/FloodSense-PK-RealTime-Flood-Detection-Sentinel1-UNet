import os
import json
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class FloodAI:
    def __init__(self):
        self.gemini_enabled = False
        self.gemini_model = None

        # Groq Init (preferred)
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key and "gsk_" in groq_key:
            try:
                self.groq_client = Groq(api_key=groq_key.strip())
                self.groq_enabled = True
            except Exception as e:
                print(f"⚠️ Groq configuration failed: {e}")
                self.groq_enabled = False
        else:
            self.groq_enabled = False

        self.enabled = self.gemini_enabled or self.groq_enabled
        if not self.enabled:
            print("⚠️ No valid AI API keys (Gemini/Groq) found. AI insights will be simulated.")

    def generate_insights(self, district_data, river_data):
        """
        Generates strategic insights based on current vs historical flood data and river flows.
        """
        prompt = f"""
        Analyze the following flood data for Pakistan and provide 4 professional strategic insights for disaster management.
        
        Compare Current Flood % (UNet Sentinel-1) with Historical 2010 Flood % (Landsat).
        
        District Data:
        {json.dumps(district_data, indent=2)}
        
        Live River Flow Data:
        {json.dumps(river_data, indent=2)}
        
        Provide concise, actionable insights focusing on:
        1. Severity compared to 2010 historical levels.
        2. Immediate relief priorities based on current inundation.
        3. Risks to infrastructure from river flows.
        4. Prediction for downstream Sindh districts.
        """
        
        if self.groq_enabled:
            try:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                print(f"Groq error: {e}")
        
        gemini_text = self._try_gemini(prompt)
        if gemini_text:
            return gemini_text

        return self._get_fallback_insights(district_data, river_data)

    def _try_gemini(self, prompt: str):
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key or gemini_key == "your-gemini-key" or len(gemini_key) <= 10:
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}")
            return None

    def _get_fallback_insights(self, district_data, river_data):
        # Fallback logic if API key is missing
        # We handle potentially missing flood_pct keys
        critical_districts = [d['district'] for d in district_data if (d.get('flood_pct_current') or d.get('flood_pct') or 0) > 5]
        high_flow_stations = [s['station'] for s in river_data if s.get('status') == 'HIGH']
        
        insights = "### AI Strategic Insights (Simulated)\n\n"
        if critical_districts:
            insights += f"1. **Deployment Priority:** Immediate relief teams should be prioritized for {', '.join(critical_districts[:3])} due to high inundation levels.\n"
        else:
            insights += "1. **Monitoring:** No districts currently exceed the critical 5% inundation threshold, but continuous monitoring is advised.\n"
            
        if high_flow_stations:
             insights += f"2. **Logistics Risk:** High river flows detected at {', '.join(high_flow_stations[:2])} may threaten nearby transport links.\n"
        else:
             insights += "2. **Infrastructure:** River flows are currently within normal ranges; however, check for localized urban flooding.\n"
             
        insights += "3. **Predictive Alert:** Maintain readiness in downstream Sindh districts as upper Indus basin shows moderate snowmelt/rainfall runoff."
        
        return insights

    def save_alert_to_json(self, alert_data):
        os.makedirs("data/json", exist_ok=True)
        path = "data/json/alerts.json"
        
        alerts = []
        if os.path.exists(path):
            with open(path, 'r') as f:
                try:
                    alerts = json.load(f)
                except:
                    alerts = []
                    
        alert_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alerts.append(alert_data)
        
        with open(path, 'w') as f:
            json.dump(alerts, f, indent=4)
