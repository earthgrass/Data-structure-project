export type Point=[number,number];
export function mapProjection(bounds:number[],width:number,height:number,padding?:number):(p:Point)=>Point;
export function polylinePoint(line:Point[],fraction:number):Point;
export function polylinePrefix(line:Point[],fraction:number):Point[];
export function pathData(line:Point[]):string;
export function layoutMapLabels(items:{id:string;point:Point;text:string}[]):Map<string,{x:number;y:number;anchor:'start'|'middle'|'end';text:string;box:{left:number;right:number;top:number;bottom:number}}>;
