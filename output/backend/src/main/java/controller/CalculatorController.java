package controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*")
public class CalculatorController {

    @PostMapping("/add")
    public int add(int a, int b) {
        return (a + b);
    }

    @PostMapping("/multiply")
    public int multiply(int a, int b) {
        return (a * b);
    }

}
