export type Point=[number,number];
export function mapProjection(bounds:number[],width:number,height:number,padding?:number):(p:Point)=>Point;
export function polylinePoint(line:Point[],fraction:number):Point;
export function polylinePrefix(line:Point[],fraction:number):Point[];
export function pathData(line:Point[]):string;
