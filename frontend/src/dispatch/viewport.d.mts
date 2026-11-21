export function projectNodes(nodes:{id:string;x:number;y:number}[],width:number,height:number):Map<string,[number,number]>;
export function fitViewport(points:[number,number][],width:number,height:number,insets?:{left:number;right:number;top:number;bottom:number}):{zoom:number;center:[number,number]};
