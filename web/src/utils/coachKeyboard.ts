/** A mobile Enter inserts a newline; composition must never submit a message. */
export function shouldSubmitCoachMessage(event: Pick<KeyboardEvent,'key'|'shiftKey'|'altKey'|'ctrlKey'|'metaKey'|'isComposing'|'keyCode'>,compact:boolean){
  return !compact && event.key==='Enter' && !event.shiftKey && !event.altKey && !event.ctrlKey && !event.metaKey && !event.isComposing && event.keyCode!==229;
}
