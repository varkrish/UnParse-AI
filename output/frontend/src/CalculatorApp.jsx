import React, { useState, useEffect } from 'react';

export default function CalculatorApp() {
  const [a, setA] = useState(0);
  const [b, setB] = useState(0);
  const [result, setResult] = useState(0);
  return (
    <div><header>Calculator App</header><div style={{marginBottom: "10px"}}><label style={{marginRight: "10px"}}>A: </label><input type="number" value={a} onChange={e => setA(e.target.value)} style={{padding: "5px", borderRadius: "4px", border: "1px solid #ccc"}} /></div><div style={{marginBottom: "10px"}}><label style={{marginRight: "10px"}}>B: </label><input type="number" value={b} onChange={e => setB(e.target.value)} style={{padding: "5px", borderRadius: "4px", border: "1px solid #ccc"}} /></div><button onClick={() => "add"(a, b, setResult)} style={{padding: "8px 15px", marginRight: "10px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: "4px", cursor: "pointer"}}>Add</button><button onClick={() => "multiply"(a, b, setResult)} style={{padding: "8px 15px", marginRight: "10px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: "4px", cursor: "pointer"}}>Multiply</button><h2 style={{marginTop: "20px", color: "#333"}} align="left">Result: {result}</h2></div>
  );
}

function add(a, b, setResult) {
  fetch(`http://localhost:8080/api/add?a=${a}&b=${b}`, {method: 'POST'}).then(res => res.json()).then(data => setResult(data));
}

function multiply(a, b, setResult) {
  fetch(`http://localhost:8080/api/multiply?a=${a}&b=${b}`, {method: 'POST'}).then(res => res.json()).then(data => setResult(data));
}

