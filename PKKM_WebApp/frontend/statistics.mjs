export const average=values=>{
  const known=values.filter(value=>typeof value==='number'&&Number.isFinite(value));
  return known.length?known.reduce((sum,value)=>sum+value,0)/known.length:null;
};
