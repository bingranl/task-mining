plugins {
    `java-gradle-plugin`
}

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(17)
    }
}

dependencies {
    testImplementation(gradleTestKit())
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.test {
    useJUnitPlatform()

    // Propagate CLI-provided system properties into the test JVM.
    val forwardedProps = listOf(
        "sample.buildFile",
        "sample.variant",
        "sample.name"
    )
    forwardedProps.forEach { key ->
        val value = System.getProperty(key)
        if (value != null) {
            systemProperty(key, value)
        }
    }
}
