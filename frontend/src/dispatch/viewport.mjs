/** Schematic affine fit from actual coordinates. O(V), no routing decisions. */
export function projectNodes(nodes,width,height){
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  for(const n of nodes){minX=Math.min(minX,n.x);maxX=Math.max(maxX,n.x);minY=Math.min(minY,n.y);maxY=Math.max(maxY,n.y);}
  return new Map(nodes.map(n=>[n.id,[maxX===minX?width/2:80+(n.x-minX)*Math.max(1,width-160)/(maxX-minX),maxY===minY?height/2:64+(n.y-minY)*Math.max(1,height-128)/(maxY-minY)]]));
}

/** Fit projected map points inside the unobscured screen rectangle. O(P). */
export function fitViewport(points,width,height,insets={left:24,right:24,top:24,bottom:24}){
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  for(const [x,y] of points){minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}
  if(!Number.isFinite(minX))return {zoom:1,center:[width/2,height/2]};
  const horizontal=Math.max(1,width-insets.left-insets.right),vertical=Math.max(1,height-insets.top-insets.bottom);
  const spanX=maxX-minX,spanY=maxY-minY;
  const zoom=spanX===0&&spanY===0?1:Math.min(8,spanX?horizontal/spanX:8,spanY?vertical/spanY:8);
  return {zoom,center:[(minX+maxX)/2+(insets.right-insets.left)/(2*zoom),(minY+maxY)/2+(insets.bottom-insets.top)/(2*zoom)]};
}
