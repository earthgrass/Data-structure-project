/** Screen-space badges, not physical positions. O(N*(N+B)*C): B obstacles, C ring/grid candidates. */
export function layoutVehicleBadges(items,obstacles=[],bounds=null){
 const occupied=[...obstacles],result=new Map();
 for(const item of items){
  const width=Math.max(88,item.text.length*7+22);let chosen;
  if(bounds&&(bounds.right-bounds.left<width||bounds.bottom-bounds.top<32))continue;
  for(let ring=0;ring<40&&!chosen;ring++)for(const [dx,dy] of [[22,-48],[-width-22,-48],[22,18],[-width-22,18],[22,-90],[-width-22,-90],[22,60],[-width-22,60]]){
   let x=item.point[0]+dx,y=item.point[1]+dy+(ring%2?-1:1)*Math.ceil(ring/2)*46;
   if(bounds){x=Math.max(bounds.left,Math.min(bounds.right-width,x));y=Math.max(bounds.top,Math.min(bounds.bottom-32,y));}
   const box={left:x,right:x+width,top:y,bottom:y+32};
   if(occupied.some(b=>box.left<b.right+8&&box.right>b.left-8&&box.top<b.bottom+8&&box.bottom>b.top-8))continue;
   chosen={x,y,width};occupied.push(box);break;
  }
  if(!chosen&&bounds)for(let y=bounds.top;y+32<=bounds.bottom&&!chosen;y+=40)for(let x=bounds.left;x+width<=bounds.right;x+=width+8){
   const box={left:x,right:x+width,top:y,bottom:y+32};
   if(occupied.some(b=>box.left<b.right+8&&box.right>b.left-8&&box.top<b.bottom+8&&box.bottom>b.top-8))continue;
   chosen={x,y,width};occupied.push(box);break;
  }
  if(chosen)result.set(item.id,chosen);
 }
 return result;
}
