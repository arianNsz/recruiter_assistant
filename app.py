import streamlit as st
import io
import pdfplumber
import google.generativeai as genai
from openai import OpenAI as oai

from langchain_core.prompts import PromptTemplate
import json

org_id=""
oai_key=""
gemini_key=""
oai_client = oai(organization=org_id, api_key=oai_key)
genai.configure(api_key=gemini_key)

from streamlit_star_rating import st_star_rating

resume_prompt_template = PromptTemplate.from_template(
    """
The text of a resume will be provided and you will extract some formatted information from it.
You are also expected to write some notes (recruiter_notes) about the resume. 
In your note you should do the followings:
- write about how you see the depth and breadth of the applicants technical skills.
- Note the impact of their work and values they have generated.
- Any specific achievements or projects that stand out to you.
- How well the resume is written and how well you think they have communicated through this resume.
- How senior and mature do you think this applicant is based on their experience and the way they have presented it in the resume.


before I list the rest of required fields please consider the following hints that might help you in extracting the information:
hint1: years of experience should be calculated based on the oldest job start date and the current date.
hint2: technical skills can be directly extracted from a list of skills or infered from previous experience and their descriptions.
hint3: seniority level can be inferred from the job titles and years of experience, please chose one of the following: junior, mid-senior, senior, lead, vp, c-level. 
hint 4: high_confidence_technical_skills is a subset of the list_of_all_technical_skills that you are confident the applicant has a good knowledge of or there is a demonstration of that in the resume.

please remember that your response MUST be formatted as a JSON object.

----------------------
following is the list of required fields:

full name:
email:
phone:
location:
latest_title:
list_of_previous_titles:
latest_company:
oldest_job_start_date:
yesrs_of_experience:
list_of_all_technical_skills:
high_confidence_technical_skills:
seniority_level:
has_team_leading_experience:
has_project_leading_experience:
has_product_leading_experience:
has_mentoring_experience:
has_research_experience:
most_recent_degree:
recruiter_notes:

----------------------
input resume:
{resume}
----------------------
your response:
"""
)

job_prompt_template = PromptTemplate.from_template(
"""
You are one of the best recruiters in the world. You are provided with a job description and you are expected to analyze it and extract some formatted information from it.
In your response you should also include a note in which you:
    - write your interpretation of the job description and what you think the company is looking for in a candidate.
    - the depth and breadth of technical skills required for the job
    - seniority level required for the job.
    - the academic qualifications and how important they are for the job.
    - domain knowledge that is clearly stated and your interpretation of other domain knowledge that might be useful/applicable to this job.
    - soft skills that is required for the job., like mentoring, negotiation, leading, corporate polictics, or anythign else that you think is important.

now, here is the complete list of what you should return. Given the job description below extract the following information in a JSON format:

job title:
list_of_technical_skills:
seniority_level: 
list_of_responsibilities:
qualification_degree:
qualification_preferred_degree:
qualification_years_of_experience:
qualification_tech_stack_experience:
qualification_domain_knowledge:
qualification_leading_experience:
qualification_research_experience:
recruiter_notes:

remember your response MUST be directly parsed as a JSON object without any modifications.
hint 1: seniority level should be one of these (junior, mid-senior, senior, lead, vp, c-level)
input job description:
{job_description}                                       

your response:
                                          
"""
)


comparison_prompt_template = PromptTemplate.from_template(
    """ 
You are one of the best recruiters in the world, and you should make a decision on whether an applicant should be considered any further or they are not a good fit for the job. 
You are provided with 2 JSON objects, one is the extracted information from the job description and the other is the extracted information from the resume.

your response MUST have 4 parts, notes, a recommendation label, a score, and a boolean flag.

In the notes section, you compare the resume info against job description info. 
I'd recommend comparing the technical skills against each other, and also comparing the recruiters notes to see if it can be a good match.
You should also mention any red flags or concerns you have about the applicant's qualifications.
Write a pros and cons list for the applicant.

The label must be one of the follwings: "A super star!🌠", "Recommended for a technical interview 📧🤙", "Recommended for a screening call 📧🤙", "No match - under qualified", "No match - over qualified"
Don't be generous with the super star label, only use it if you are really impressed. But it is OK to recommend for a technical interview with a score of 5 if you think they are a solid match.


the score must be between 1-5 based on how well they match the job description. 5 is the best match, 1 is the worst. 
if you recommend them for technical interview their score must be 4 or 5, depending how strong their technical background seems to be and how relevant their experience is to the job description.
if you recommend them for a screening call, their score must be 3 or 4, again depending how strong their technical background seems to be and how relevant their experience is to the job description.
In RARE cases you recommend that the applicant is a super star, naturally their score must be 5.
if you recommend that the applicant is under qualified, their score must be 1 or 2.
if you recommend that the applicant is over qualified, their score must be 2.
don't reserve 5 for super stars only, if you are recommending for a technical interview and the applicant seems to have a strong background, you can give them a 5.


Finally, the flag is True only if the applicant name is 'Arian Naseh' (which is me!). If my resume is passed then flag it! 

hint 1: if required degree is Bachlor, but PhD is stated preferred degree, and the applicant has a M.Sc degree, it means the applicant has better than the required qualifications, and it is also considered as a bonous.
hint 2: "Advanced degree" can refer to a Master's degree or higher.
hint 3: if the job description is asking for 3+ years of experience and the applicant has 10 years of experience, it usually means the applicant is over qualified.
hint 4: if absolute majority of the technical skills in the job description cannot be found among the high_confidence_technical_skills of resume, be cautious about recommending the applicant for a technical interview.
-----
required fields in the output are:

notes:
label:
score:
is_arian_naseh:
-----
job description info:
{jd_json}

-----
resume info:
{resume_json}

-----
your response:

"""
)

MAX_RETRY = 3


def get_response(prompt):
    response = oai_client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return response.choices[0].message.content


def check_length():
    text = st.session_state["job_description"]
    if len(text) < 300:
        st.warning(
            "Job description is too short! Please provide a detailed description which is at least 300 characters.",
            icon="⚠️",
        )


def analysis(resume: str, job_description: str):
    """
    Analyzes the resume and job description to compare the applicant's qualifications with the job requirements.

    Args:
        resume (str): The uploaded resume in string format.
        job_description (str): The job description in string format.

    Returns:
        str: The comparison response indicating the match between the applicant's qualifications and the job requirements.
    """
    with st.status("Analyzing...", expanded=True) as status:
        comparison_response = None

        st.write("Processing the uploaded resume...")
        for i in range(MAX_RETRY):
            try:
                resume_prompt = resume_prompt_template.format(resume=resume)
                resume_response = get_response(resume_prompt)
                print(resume_response)
                print("---------------------")
                break
            except:
                if i == MAX_RETRY - 1:
                    st.error(
                        f"Failed to process the resume after {MAX_RETRY} tries. Please make sure the uploaded pdf is not a scanned document or try again with another file."
                    )
        st.write("Analyzing the job description...")
        for i in range(MAX_RETRY):
            try:
                job_prompt = job_prompt_template.format(
                    job_description=job_description
                )
                jd_response = get_response(job_prompt)
                print(jd_response)
                print("---------------------")
                break
            except:
                if i == MAX_RETRY - 1:
                    st.error(
                        f"Failed to process the job description after {MAX_RETRY} tries. Make sure it is English or maybe change it slightly and try again."
                    )
        st.write("Comparing applicants qualifications with the job description...")
        for i in range(MAX_RETRY):
            try:
                comparison_prompt = comparison_prompt_template.format(
                    jd_json=jd_response,
                    resume_json=resume_response,
                )
                print(comparison_prompt)
                comparison_response = get_response(comparison_prompt)
                print(comparison_response)
                print("---------------------")
                break
            except:
                if i == MAX_RETRY - 1:
                    st.error(
                        f"Failed to compare the documents after {MAX_RETRY} tries. Please make some changes to the inputs and try again."
                    )
            status.update(label="Analysis complete!", state="complete", expanded=False)
        return comparison_response


def process_button_clicked(resume, job_description):
    if not resume or len(job_description) < 300:
        st.error(
            "Please ensure a resume is uploaded and the job description is at least 300 characters long."
        )
    else:
        return analysis(resume, job_description)


def main():
    st.title("Recruiter Assistant!")
    st.markdown(
        "This **DEMO** app will help you to find the best candidates for your job description!"
    )
    st.write(
        "Simply enter the job description below and upload the resume you have at hand and get a quick rating and recommendation!"
    )


    job_description = st.text_area(
        label="Job Description",
        key="job_description",
        placeholder="The job description must be at least 300 characters. Please inlcude the job title.",
        on_change=check_length,
        height = 320
    )


    uploaded_resume = st.file_uploader(
        "Upload the resume in pdf format.", accept_multiple_files=False, type="pdf"
    )

    if uploaded_resume:
        bytes_data = uploaded_resume.getvalue()
        resume = ""
        with pdfplumber.open(io.BytesIO(bytes_data)) as pdf:
            if len(pdf.pages) < 2:
                resume = pdf.pages[0].extract_text()
            else:
                for i in range(2):
                    resume += "\n" + pdf.pages[i].extract_text()


    clicked = st.button(label="Process", type="primary")
    results = None
    if clicked:
        results = process_button_clicked(resume, job_description)

        if results:
            results = json.loads(results)
            if results['is_arian_naseh'] in (True, "True", "true"):
                st.markdown("#### Well, of course I'd recommend Arian!🤩🌟 \n#### He has built this tool you're using!🤓")
                st.markdown("#### But since we are professionals, here is our regular analysis:")
            
            st_star_rating(label = "Match Rating", maxValue = 5, defaultValue = results['score'], key = "match_rating", read_only = True )
            st.markdown(f"#### Our recommendation: \n {results['label']}")
            st.markdown(f"#### What we noted: \n {results['notes']}")




if __name__ == "__main__":
    main()
