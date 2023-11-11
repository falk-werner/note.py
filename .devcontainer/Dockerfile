FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y --no-install-recommends \
    ca-certificates \
    git \
    openssh-client \
    python3 \
    python3-pip \
    python3-tk \
    graphviz

RUN pip install pytest pylint coverage

ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
RUN rm /tmp/requirements.txt

ADD doc/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
RUN rm /tmp/requirements.txt

ARG USERNAME=user
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME
RUN useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

USER $USERNAME