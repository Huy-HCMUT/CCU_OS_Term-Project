FROM ghcr.io/arduino/app-bricks/python-apps-base:0.12.0
USER root
RUN python3 -m pip install --no-cache-dir onnxruntime==1.31.1 onnx==1.23.2
COPY make_model.py analytics_node.py /opt/realload/
RUN python3 /opt/realload/make_model.py --out /opt/realload/models --widths 64,128,192,256,384 && chmod -R a+rX /opt/realload
USER arduino
ENTRYPOINT ["python3", "/opt/realload/analytics_node.py"]

