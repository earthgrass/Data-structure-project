/** Schematic affine fit from actual coordinates. O(V), no routing decisions. */
export function projectNodes(nodes,width,height){
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  for(const n of nodes){minX=Math.min(minX,n.x);maxX=Math.max(maxX,n.x);minY=Math.min(minY,n.y);maxY=Math.max(maxY,n.y);}
  return new Map(nodes.map(n=>[n.id,[maxX===minX?width/2:80+(n.x-minX)*Math.max(1,width-160)/(maxX-minX),maxY===minY?height/2:64+(n.y-minY)*Math.max(1,height-128)/(maxY-minY)]]));
}
