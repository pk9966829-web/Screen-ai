export {};
type VoiceCredential={device_id:string;device_token:string;platform:string};
type RecognitionInstance={lang:string;continuous:boolean;interimResults:boolean;maxAlternatives:number;onresult:((event:any)=>void)|null;onerror:((event:any)=>void)|null;onend:(()=>void)|null;start:()=>void;stop:()=>void};
type RecognitionConstructor=new()=>RecognitionInstance;
declare global{interface Window{__TAURI__?:any;SpeechRecognition?:RecognitionConstructor;webkitSpeechRecognition?:RecognitionConstructor}}
const API="http://127.0.0.1:8001";
const invoke=window.__TAURI__?.core?.invoke as ((command:string,args?:Record<string,unknown>)=>Promise<any>)|undefined;
const statusElement=document.getElementById("status"),transcriptBox=document.getElementById("transcript"),replyBox=document.getElementById("reply");
const talkButton=document.getElementById("talk") as HTMLButtonElement|null,stopButton=document.getElementById("stop-speaking") as HTMLButtonElement|null,closeButton=document.getElementById("close") as HTMLButtonElement|null;
const textForm=document.getElementById("text-form") as HTMLFormElement|null,textInput=document.getElementById("text-input") as HTMLInputElement|null,voiceOrb=document.getElementById("voice-orb");
let recognition:RecognitionInstance|null=null,busy=false;
function setStatus(message:string){if(statusElement)statusElement.textContent=message}
function setListening(active:boolean){voiceOrb?.classList.toggle("listening",active);if(talkButton){talkButton.disabled=active||busy;talkButton.textContent=active?"Listening...":"Start speaking"}}
async function readDesktopCredential():Promise<VoiceCredential>{
 if(!invoke)throw new Error("Open VOSI in its Windows desktop app to use voice.");
 const raw=await invoke("load_agent_device_credential");if(!raw)throw new Error("This PC is not paired yet. Pair it in VOSI Connectors first.");
 let credential:VoiceCredential;try{credential=JSON.parse(String(raw)) as VoiceCredential}catch{throw new Error("Saved PC pairing is invalid. Disconnect and pair this PC again.")}
 if(!credential.device_token||credential.platform!=="desktop")throw new Error("A valid paired Windows PC credential is required.");return credential
}
function speak(text:string){if(!("speechSynthesis"in window)||!text.trim())return;window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text);utterance.lang="en-IN";utterance.rate=1;window.speechSynthesis.speak(utterance)}
async function sendToVosi(message:string){
 const clean=message.trim();if(!clean||busy)return;busy=true;if(talkButton)talkButton.disabled=true;if(textInput)textInput.disabled=true;if(transcriptBox)transcriptBox.textContent=clean;setStatus("VOSI is thinking...");
 try{const credential=await readDesktopCredential();const response=await fetch(API+"/companion/voice",{method:"POST",headers:{"Authorization":"Bearer "+credential.device_token,"Content-Type":"application/json"},body:JSON.stringify({transcript:clean})});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(String(payload.detail||"VOSI backend returned HTTP "+response.status));const answer=String(payload.response||"I couldn't prepare a reply.");if(replyBox)replyBox.textContent=answer;setStatus(payload.success?"VOSI replied":"AI provider needs attention");speak(answer)}
 catch(error){const messageText=error instanceof Error?error.message:String(error);if(replyBox)replyBox.textContent=messageText;setStatus("Connection or pairing issue")}
 finally{busy=false;if(talkButton)talkButton.disabled=false;if(textInput)textInput.disabled=false}
}
function startListening(){
 const SpeechRecognitionApi=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SpeechRecognitionApi){setStatus("Speech recognition is unavailable here. Type your message below instead.");return}if(busy||recognition)return;
 try{const activeRecognition=new SpeechRecognitionApi();recognition=activeRecognition;activeRecognition.lang="en-IN";activeRecognition.continuous=false;activeRecognition.interimResults=false;activeRecognition.maxAlternatives=1;
 activeRecognition.onresult=(event:any)=>{const result=event.results?.[event.results.length-1]?.[0];const spoken=String(result?.transcript||"").trim();if(spoken)void sendToVosi(spoken)};
 activeRecognition.onerror=(event:any)=>{const reason=String(event.error||"unknown");setStatus(reason==="not-allowed"?"Microphone permission was denied. Allow it in Windows privacy settings.":"Speech recognition stopped: "+reason)};
 activeRecognition.onend=()=>{recognition=null;setListening(false);if(!busy&&statusElement?.textContent==="Listening...")setStatus("Ready when you are")};setListening(true);setStatus("Listening...");activeRecognition.start()}
 catch(error){recognition=null;setListening(false);setStatus("Could not start speech recognition: "+String(error))}
}
talkButton?.addEventListener("click",startListening);
stopButton?.addEventListener("click",()=>window.speechSynthesis?.cancel());
textForm?.addEventListener("submit",(event)=>{event.preventDefault();const message=textInput?.value||"";if(textInput)textInput.value="";void sendToVosi(message)});
closeButton?.addEventListener("click",async()=>{recognition?.stop();window.speechSynthesis?.cancel();if(invoke){try{await invoke("hide_voice_companion")}catch(error){setStatus("Could not close voice panel: "+String(error))}}});
if(!invoke)setStatus("Open VOSI in the Windows desktop app to connect your paired PC.");
else void readDesktopCredential().then(()=>setStatus("PC paired. Ready when you are.")).catch(error=>setStatus(error instanceof Error?error.message:String(error)));
