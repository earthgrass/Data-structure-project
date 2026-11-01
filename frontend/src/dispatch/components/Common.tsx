import {useEffect,useRef,type ReactNode} from 'react';
export function Icon({name,size=20}:{name:string;size?:number}){
  const paths:Record<string,ReactNode>={
    overview:<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    fleet:<><path d="M3 6h11v11H3zM14 10h4l3 4v3h-7"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></>,
    orders:<><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3h6v4H9zM9 12h6M9 16h4"/></>,
    inventory:<><path d="m3 8 9-5 9 5v13H3zM3 8l9 5 9-5M12 13v8M8 5l9 5"/></>,
    traffic:<><path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2zM9 3v16M15 5v16"/></>,
    audit:<><path d="M12 3 3 7v6c0 4 9 8 9 8s9-4 9-8V7z"/><path d="m8 12 3 3 5-6"/></>,
    arrow:<path d="m5 12 14 0m-6-6 6 6-6 6"/>,
    pin:<><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/></>,
    clock:<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]??paths.overview}</svg>;
}
export function Badge({children,tone='neutral'}:{children:ReactNode;tone?:string}){return <span className={'d-badge '+tone}>{children}</span>;}
export function Empty({title,children}:{title:string;children?:ReactNode}){return <div className="d-empty"><Icon name="traffic" size={40}/><h2>{title}</h2><p>{children}</p></div>;}
export type Confirmation={title:string;description:string;confirm:string;action:()=>void};
export function ConfirmDialog({value,close}:{value:Confirmation|null;close:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(value)dialog.current?.showModal();else dialog.current?.close();},[value]);
  return <dialog ref={dialog} className="d-confirm" aria-labelledby="confirm-title" onCancel={close}>
    {value&&<><h2 id="confirm-title">{value.title}</h2><p>{value.description}</p><div className="d-actions"><button onClick={close} autoFocus>返回</button><button className="d-primary" onClick={()=>{value.action();close();}}>{value.confirm}</button></div></>}
  </dialog>;
}
