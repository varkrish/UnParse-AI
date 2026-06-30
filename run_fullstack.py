import sys
import os
import shutil
import subprocess

from schema import init_db, DB_PATH
from agent import run_agent
from java_unparser import build_java_file, unparse_pom, _q
from react_unparser import build_react_file

JAVA_OUTPUT = os.path.join(os.path.dirname(__file__), "output", "backend")
REACT_OUTPUT = os.path.join(os.path.dirname(__file__), "output", "frontend")

PROMPT = "Create a full stack calculator app using React and Java."

def main():
    print("=" * 60)
    print("  AST-Agent: Full Stack Generation")
    print("=" * 60)

    if os.path.exists(DB_PATH):
        if os.path.isdir(DB_PATH):
            shutil.rmtree(DB_PATH)
        else:
            os.remove(DB_PATH)
    db, conn = init_db()

    print("\n  🤖 Running AST-Agent on a single high-level full-stack prompt...")
    run_agent(conn, PROMPT)
        
    print("\n─" * 20)
    print("Stage 3: Scaffolding & Unparsing Full Stack Code")
    
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Scaffolding Java Backend with Maven Archetype
    if os.path.exists(JAVA_OUTPUT):
        shutil.rmtree(JAVA_OUTPUT)
        
    print("  ☕ Scaffolding Java Backend with Maven Archetype...")
    # Get JAVA_HOME dynamically
    java_home = subprocess.check_output(["/usr/libexec/java_home"]).decode().strip()
    subprocess.run([
        "mvn", "archetype:generate",
        "-DgroupId=com.unparse.generated",
        "-DartifactId=backend",
        "-DarchetypeArtifactId=maven-archetype-quickstart",
        "-DinteractiveMode=false"
    ], env={**os.environ, "JAVA_HOME": java_home}, cwd=output_dir, capture_output=True)
    
    # Clean up App.java created by maven quickstart
    default_app = os.path.join(JAVA_OUTPUT, "src/main/java/com/unparse/generated/App.java")
    if os.path.exists(default_app):
        os.remove(default_app)
        
    # Discover modules dynamically
    rows = _q(conn, "MATCH (m:Module) RETURN m.id, m.name")
    controller_id = None
    app_id = None
    ui_id = None
    
    for r in rows:
        name = r["m.name"]
        mid = r["m.id"]
        if "controller" in name.lower():
            controller_id = mid
        elif "application" in name.lower():
            app_id = mid
        elif "app" in name.lower():
            ui_id = mid

    if not controller_id or not app_id or not ui_id:
        print(f"❌ Error: Could not discover all modules. Found rows: {rows}")
        sys.exit(1)

    # Unparse Java files over the scaffold
    java_code = build_java_file(conn, controller_id)
    java_path = os.path.join(JAVA_OUTPUT, "src/main/java/controller/CalculatorController.java")
    os.makedirs(os.path.dirname(java_path), exist_ok=True)
    with open(java_path, "w") as f:
        f.write(java_code)
        
    # Generate Application.java DYNAMICALLY from Kuzu AST graph
    app_code = build_java_file(conn, app_id)
    app_path = os.path.join(JAVA_OUTPUT, "src/main/java/com/unparse/generated/Application.java")
    os.makedirs(os.path.dirname(app_path), exist_ok=True)
    with open(app_path, "w") as f:
        f.write(app_code)
        
    # Overwrite pom.xml
    pom_xml = unparse_pom(conn, JAVA_OUTPUT)
    pom_path = os.path.join(JAVA_OUTPUT, "pom.xml")
    with open(pom_path, "w") as f:
        f.write(pom_xml)
        
    print(f"✅ Generated Java Spring Boot App inside {JAVA_OUTPUT}")
    
    # 2. Scaffolding React Frontend with Vite
    if os.path.exists(REACT_OUTPUT):
        shutil.rmtree(REACT_OUTPUT)
        
    print("  ⚛️ Scaffolding React Frontend with Vite...")
    subprocess.run(["npx", "-y", "create-vite@latest", "frontend", "--template", "react"], cwd=output_dir, capture_output=True)
    
    # Write React component
    react_code = build_react_file(conn, ui_id)
    react_path = os.path.join(REACT_OUTPUT, "src/CalculatorApp.jsx")
    os.makedirs(os.path.dirname(react_path), exist_ok=True)
    with open(react_path, "w") as f:
        f.write(react_code)
        
    # Patch main.jsx or App.jsx to render our app
    app_jsx = os.path.join(REACT_OUTPUT, "src/App.jsx")
    with open(app_jsx, "w") as f:
        f.write("import CalculatorApp from './CalculatorApp';\nexport default function App() { return <CalculatorApp />; }")
        
    print(f"✅ Generated React Component inside {REACT_OUTPUT}")

    # 3. Link Full Stack Boundaries in the AST Database
    print("\n🔗 Linking cross-stack REST APIs in the graph database...")
    link_fullstack_endpoints(conn)

def link_fullstack_endpoints(conn):
    # Retrieve Java controller functions
    controllers = _q(conn, "MATCH (m:Module)-[:HAS_FUNCTION_Module]->(f:Function) WHERE m.name = 'controller/CalculatorController' RETURN f.id, f.name, f.decorators")
    
    # Retrieve UI functions
    ui_funcs = _q(conn, "MATCH (m:Module)-[:HAS_FUNCTION_Module]->(f:Function) WHERE m.name = 'ui/CalculatorApp' RETURN f.id, f.name")
    
    for c in controllers:
        c_id = c["f.id"]
        c_name = c["f.name"]
        decorators = c["f.decorators"] or ""
        
        # Parse path & method
        method = "POST" if "@PostMapping" in decorators else "GET"
        path = "/api"
        for line in decorators.split("\n"):
            if "@RequestMapping" in line:
                # E.g. @RequestMapping("/api") -> /api
                parts = line.split('"')
                if len(parts) > 1:
                    path = parts[1]
            if "Mapping" in line:
                parts = line.split('"')
                if len(parts) > 1:
                    path += parts[1]
                    
        for u in ui_funcs:
            u_id = u["f.id"]
            u_name = u["f.name"]
            
            if u_name.lower() == c_name.lower():
                print(f"   ⚡ Linked: React '{u_name}()' ──► Java REST Endpoint '{path}' ({method})")
                conn.execute(
                    "MATCH (a:Function {id: $a_id}), (b:Function {id: $b_id}) "
                    "MERGE (a)-[:CALLS_API {path: $path, method: $method}]->(b)",
                    {"a_id": u_id, "b_id": c_id, "path": path, "method": method}
                )

if __name__ == "__main__":
    main()
