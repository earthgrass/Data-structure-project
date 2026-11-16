export type Point=[number,number];
export function mapProjection(bounds:number[],width:number,height:number,padding?:number):(p:Point)=>Point;
export function polylinePoint(line:Point[],fraction:number):Point;
export function polylinePrefix(line:Point[],fraction:number):Point[];
export function pathData(line:Point[]):string;
export type LabelBox={left:number;right:number;top:number;bottom:number};
export function layoutMapLabels(items:{id:string;point:Point;text:string}[],obstacles?:readonly LabelBox[]):Map<string,{x:number;y:number;anchor:'start'|'middle'|'end';text:string;box:LabelBox}>;
