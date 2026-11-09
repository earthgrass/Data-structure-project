/** Map geometry only: uniform Mercator fit and arc-length interpolation. No routing. */
export function mapProjection(bounds,width,height,padding=80){
  const [x0,y0,x1,y1]=bounds;
  const scale=Math.min(Math.max(1,width-padding*2)/Math.max(1,x1-x0),Math.max(1,height-padding*2)/Math.max(1,y1-y0));
  return ([x,y])=>[width/2+(x-(x0+x1)/2)*scale,height/2+(y-(y0+y1)/2)*scale];
}
export function polylinePoint(line,fraction){
  if(!line.length)return [0,0];
  let total=0;const lengths=[];
  for(let i=1;i<line.length;i++){const d=Math.hypot(line[i][0]-line[i-1][0],line[i][1]-line[i-1][1]);lengths.push(d);total+=d;}
  let remaining=Math.max(0,Math.min(1,fraction))*total;
  for(let i=0;i<lengths.length;i++){if(remaining<=lengths[i]&&lengths[i]>0){const p=remaining/lengths[i];return [line[i][0]+(line[i+1][0]-line[i][0])*p,line[i][1]+(line[i+1][1]-line[i][1])*p];}remaining-=lengths[i];}
  return line[line.length-1];
}
export function polylinePrefix(line,fraction){
  if(!line.length)return [];
  const endpoint=polylinePoint(line,fraction);let total=0;
  for(let i=1;i<line.length;i++)total+=Math.hypot(line[i][0]-line[i-1][0],line[i][1]-line[i-1][1]);
  let remaining=Math.max(0,Math.min(1,fraction))*total;const result=[line[0]];
  for(let i=1;i<line.length;i++){const d=Math.hypot(line[i][0]-line[i-1][0],line[i][1]-line[i-1][1]);if(d>remaining)break;result.push(line[i]);remaining-=d;}
  result.push(endpoint);return result;
}
export function pathData(line){return line.map((p,i)=>`${i?'L':'M'}${p[0]},${p[1]}`).join(' ');}

/** Greedy screen-space label placement; Time O(N²), Space O(N), stable input order. */
export function layoutMapLabels(items){
  const occupied=[],result=new Map();
  for(const item of items){
    let width=0;for(const ch of item.text)width+=ch.codePointAt(0)>255?11:7;
    for(const [x,y,anchor] of [[0,-27,'middle'],[20,4,'start'],[-20,4,'end'],[0,34,'middle']]){
      const left=item.point[0]+x-(anchor==='middle'?width/2:anchor==='end'?width:0);
      const box={left:left-5,right:left+width+5,top:item.point[1]+y-15,bottom:item.point[1]+y+5};
      if(occupied.some(b=>box.left<b.right&&box.right>b.left&&box.top<b.bottom&&box.bottom>b.top))continue;
      occupied.push(box);result.set(item.id,{x,y,anchor,text:item.text,box});break;
    }
  }
  return result;
}
