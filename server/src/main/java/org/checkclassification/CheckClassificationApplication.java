package org.checkclassification;

 // CheckClassificationApplication

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("org.checkclassification.mapper")
public class CheckClassificationApplication {

    public static void main(String[] args) {
        SpringApplication.run(CheckClassificationApplication.class, args);
    }

}
