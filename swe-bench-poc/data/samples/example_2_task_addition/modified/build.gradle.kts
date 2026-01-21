tasks.register("hello") {
    doLast {
        println("hello")
    }
}

tasks.register("generateDocs") {
    doLast {
        println("Generating docs")
    }
}
