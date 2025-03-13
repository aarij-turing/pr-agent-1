import os
import sys
import asyncio
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, URL

# Add the parent directory to the path so we can import from pr_agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pr_agent.tools.pr_deployment_impact import PRDeploymentImpact
from pr_agent.config_loader import get_settings

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-flask-app')

class PRUrlForm(FlaskForm):
    pr_url = StringField('PR URL', validators=[DataRequired(), URL()])
    submit = SubmitField('Analyze Deployment Impact')

@app.route('/', methods=['GET', 'POST'])
def index():
    form = PRUrlForm()
    if form.validate_on_submit():
        pr_url = form.pr_url.data
        return redirect(url_for('analyze', pr_url=pr_url))
    return render_template('index.html', form=form)

@app.route('/analyze')
def analyze():
    pr_url = request.args.get('pr_url')
    if not pr_url:
        flash('PR URL is required', 'error')
        return redirect(url_for('index'))
    
    return render_template('analysis.html', pr_url=pr_url)

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.json
    pr_url = data.get('pr_url')
    
    if not pr_url:
        return jsonify({'error': 'PR URL is required'}), 400
    
    try:
        # Disable publishing output to the PR
        get_settings().config.publish_output = False
        
        # Create an instance of PRDeploymentImpact
        deployment_impact = PRDeploymentImpact(pr_url, cli_mode=True)
        
        # Run the analysis asynchronously
        result = asyncio.run(run_analysis(deployment_impact))
        
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

async def run_analysis(deployment_impact):
    # Run the deployment impact analysis
    await deployment_impact.run()
    
    # Get the analysis result from the settings data
    if hasattr(get_settings(), 'data') and 'artifact' in get_settings().data:
        return get_settings().data['artifact']
    else:
        return "No analysis result available"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
