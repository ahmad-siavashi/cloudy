# Cloudy: a modern simulator of cloud environments

Cloudy is a framework for modeling and simulating cloud computing environments and services. It enables the creation of
virtualized cloud computing environments, and provides a comprehensive set of features for simulating and analyzing the
performance of cloud infrastructures. The goal is to enable researchers and developers to evaluate the performance of
their cloud-based applications and services in a realistic simulated environment. The simulator is a valuable tool for
developers, allowing them to test their applications and services in a realistic environment without the need for a
physical cloud environment. The simulator is designed to support a range of cloud service models, providing flexibility
and applicability across various cloud-based scenarios.

## Getting started

The simulator is designed to be easy to use and extend. To run Cloudy,

1. Clone the project

    ```bash 
    $ git clone https://github.com/ahmad-siavashi/cloudy.git 
    ```

2. Install [Python 3.10](https://wiki.python.org/moin/BeginnersGuide/Download)

3. Install dependencies
     ```bash
     $ pip install -r requirements.txt
     ```

4. Set up `PYTHONPATH` environment variable
    - Determine the path to your project source root directory (where `cloudy/src` is located).
   #### Windows PowerShell
     ```powershell
     $env:PYTHONPATH = "<path_to_project_root>;$env:PYTHONPATH"
     ```

   #### Windows Command Prompt (CMD)
     ```batch
     set PYTHONPATH=<path_to_project_root>;%PYTHONPATH%
     ```
   #### Linux (Bash)
     ```bash
     export PYTHONPATH=<path_to_project_root>:$PYTHONPATH
     ```

   **Note:** _Depending on your operating system and shell environment, you may need to replace backslashes with double
   backslashes when setting the `PYTHONPATH` variable on Windows. For example, if the path to your project root
   directory is `C:\path\to\cloudy\src`, you should set the `PYTHONPATH` variable as `C:\\path\\to\\cloudy\\src"` in Windows
   environments. This is due to the way backslashes are treated as escape characters in certain contexts. Linux
   environments do not require this adjustment._

5. Run an example
      ```bash
      $ python3 basic_example.py
      ```

That's all. The code is minimal, self-documented and easy to read. You can quickly start coding by reading the existing
code and example. Nevertheless, documentations are provided in the `doc` directory.

## Examples

Explore the capabilities of Cloudy by checking out the examples in the `examples` directory. These examples demonstrate
some use cases and functionalities of the simulator.

## Contribution

The simulator is a work in progress. Please feel free to develop new features or make improvements. You can contact me
through email at siavashi@aut.ac.ir. For ensuring the reliability of the codebase, limited unit tests are available in
the `tests` directory. You are
encouraged to add more tests as you contribute to the project.

**Generating HTML Documentation with PyDoctor**

To generate HTML documentation for the Python code using PyDoctor, run the following command in the terminal or command
prompt while you are within the project root directory, i.e. cloudy:

```bash
$ pip install pydoctor
$ pydoctor --project-name cloudy --html-output ./docs/ --docformat=numpy ./src/model/ ./src/module/ ./src/policy/
```

PyDoctor will analyze the code and generate the HTML documentation, which can be accessed in the
specified `doc` directory. The docstrings are written
with [numpy style](https://numpydoc.readthedocs.io/en/latest/format.html).

**Event Queue System**

The simulator enjoys an event-driven architecture empowered by [evque](https://github.com/ahmad-siavashi/evque)
and [cloca](https://github.com/ahmad-siavashi/cloca) Python libraries implemented by the creator. The event queue system
is a powerful and flexible mechanism designed to manage and process events in a distributed
application. It serves as a central hub for event communication, enabling different components and instances to interact
efficiently and asynchronously. This document provides an overview of the system's functionality, explains its core
topics, and guides users on how to extend the system to suit their specific requirements.

At its core, the event queue system facilitates communication between various parts of a distributed application by
utilizing the publish-subscribe pattern. It enables decoupling of components, ensuring that they can communicate without
being aware of each other's existence. This decoupling fosters modularity and scalability, making the system highly
adaptable to complex applications.

The system revolves around the concept of topics, which act as channels for event messages. Publishers, the entities
generating events, send messages to specific topics without the need to know who, if anyone, is listening. Subscribers,
on the other hand, express their interest in specific topics and receive messages whenever events are published to those
topics.

### Topics and Purpose

The following elucidates the primary event topics used within the Cloudy simulator, offering a brief description of their significance and the scenarios in which they are employed:

- **request.arrive**: Signifies the arrival of a request. It also keeps track of model-based requests, recording the count in the simulator's tracker.
  
- **request.accept**: Indicates that a request has been accepted and this acceptance is recorded in the simulator's tracker.

- **request.reject**: Denotes that a request has been rejected, and this rejection is recorded in the simulator's tracker.

- **request.stop**: Signifies the stopping or completion of a request, and this stop event is recorded in the simulator's tracker.

- **action.execute**: Handles the execution of a list of actions. The specific processing logic is determined by the associated handler function.

- **app.start**: Marks the start of an application on a specific virtual machine (VM).

- **app.stop**: Indicates the stopping of an application on a specific VM.

- **container.start**: Denotes the start of a container on a specific VM.

- **container.stop**: Signifies the stopping of a container on a specific VM.

- **controller.start**: Marks the start of a controller on a specific VM.

- **controller.stop**: Indicates the stopping of a controller on a specific VM.

- **deployment.run**: Highlights when a deployment is in a RUNNING state.

- **deployment.pend**: Implies that a deployment is in a PENDING state, awaiting resources.

- **deployment.degrade**: Points out when a deployment is DEGRADED with a specified number of replicas remaining.

- **deployment.scale**: Marks when a deployment has been scaled, either with replicas added or deleted.

- **deployment.stop**: Specifies when a deployment is STOPPED.

- **vm.allocate**: Signifies the allocation of a VM to a physical machine (PM).

- **vm.deallocate**: Marks the deallocation or release of a VM from a physical machine (PM).

- **sim.log**: Pertains to the general logging mechanism of the simulation. The specific processing logic is determined by the associated handler function.

The event queue system is designed with extensibility in mind, allowing developers to add new functionalities and tailor
it to their specific needs. Here are some guidelines to follow when extending the system:

1. **Define New Topics:** Identify the new events or functionalities you want to introduce and create descriptive topic
   names for each.

2. **Publish to Appropriate Topics:** Ensure that new components or instances publish messages to the relevant topics
   based on their functionalities.

3. **Implement Subscribers:** Create subscribers for the new topics to handle events effectively. Subscribers can
   process data, trigger actions, or update the system's state.

4. **Maintain Consistency:** Keep the new extensions consistent with existing conventions and patterns in the event
   queue system. Consistency enhances code readability and collaboration.

5. **Error Handling:** Implement error handling mechanisms for critical operations to ensure stability and graceful
   recovery from exceptions.

6. **Performance Optimization:** Monitor system performance and optimize event handling as needed, such as implementing
   asynchronous processing or load balancing.

By following these guidelines, developers can seamlessly integrate new features into the event queue system, enhancing
its capabilities and supporting diverse applications.
