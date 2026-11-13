package org.checkclassification.pojo.entity;

 // PatientMedicalInfo

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName(value = "patient_medical_info", autoResultMap = true)
public class PatientMedicalInfo {

    @TableId(value = "uid", type = IdType.INPUT)
    private String uid;

    @TableField(value = "name", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private String name;

    @TableField(value = "sex", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer sex;

     // 年龄
    @TableField(value = "age", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer age;

    @TableField(value = "blood", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private String blood;

    @TableField(value = "is_trauma_injury", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Boolean isTraumaInjury;

    @TableField(value = "head_injury", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Boolean headInjury;

    @TableField(value = "left_arm", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Boolean leftArm;

    @TableField(value = "right_arm", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Boolean rightArm;

    @TableField(value = "left_leg", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Boolean leftLeg;

    @TableField(value = "right_leg", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Boolean rightLeg;

    @TableField(value = "chest", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Boolean chest;

    @TableField(value = "abdomen", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Boolean abdomen;

    @TableField(value = "glasgow", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer glasgow;

     // PHI总分（院前指数）
    @TableField(value = "phi", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer phi;

    @TableField(value = "start_color", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private String startColor;

    @TableField(value = "crams", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer crams;

     // 心率指标
    @TableField(value = "heart_rate", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer heartRate;

    @TableField(value = "systolic_pressure", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer systolicPressure;

    @TableField(value = "diastolic_pressure", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer diastolicPressure;

     // 呼吸频率
    @TableField(value = "respiratory_rate", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer respiratoryRate;

     // 血氧饱和度
    @TableField(value = "oxygen_saturation", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer oxygenSaturation;

    @TableField(value = "temperature", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private BigDecimal temperature;

    @TableField(value = "vital_timestamp", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private String vitalTimestamp;

    @TableField(value = "suggestion", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer suggestion;

    // ========== 新字段：使用ALWAYS策略强制插入/更新 ==========
     // GCS睁眼反应分数（细分字段）
    @TableField(value = "gcs_eye_opening", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer gcsEyeOpening;

    @TableField(value = "gcs_verbal_response", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer gcsVerbalResponse;

     // GCS运动反应分数（细分字段）
    @TableField(value = "gcs_motor_response", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer gcsMotorResponse;

    @TableField(value = "phi_systolic_pressure", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer phiSystolicPressure;

     // PHI脉搏分数（细分字段）
    @TableField(value = "phi_pulse", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer phiPulse;

    @TableField(value = "phi_breathing", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer phiBreathing;

    @TableField(value = "phi_consciousness", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer phiConsciousness;

     // CRAMS呼吸分数（细分字段）
    @TableField(value = "crams_breath", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer cramsBreath;

    @TableField(value = "crams_chest", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer cramsChest;

     // CRAMS意识分数
    @TableField(value = "crams_sport", insertStrategy = FieldStrategy.ALWAYS, updateStrategy = FieldStrategy.ALWAYS)
    private Integer cramsSport;

     // 记录创建时间（自动填充）
    @TableField(value = "create_time", fill = FieldFill.INSERT)
    private LocalDateTime createTime;

     // 记录更新时间（自动填充）
    @TableField(value = "update_time", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
