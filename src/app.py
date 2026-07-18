"""Main Streamlit application for the Personalized Digest System."""
import streamlit as st
import json
from datetime import datetime, timezone
from database import (
    init_db, get_db, seed_default_interests,
    Member, Interest, Document, Digest, SchedulerConfig, EmailQueue
)
from llm_service import LLMService
from wordpress_fetcher import WordPressFetcher
from email_service import EmailService
from email_queue_processor import EmailQueueProcessor
from scheduler_service import DigestScheduler
from logger_utils import log

# Initialize database
init_db()

# Page config
st.set_page_config(
    page_title="Personalized Digest System",
    page_icon="📰",
    layout="wide"
)

# Initialize LLM service
@st.cache_resource
def get_llm_service():
    return LLMService()

llm_service = get_llm_service()

# Initialize session state
if 'current_member' not in st.session_state:
    st.session_state.current_member = None
if 'fetched_posts' not in st.session_state:
    st.session_state.fetched_posts = None
if 'processing_started' not in st.session_state:
    st.session_state.processing_started = False

def main():
    st.title("📰 Personalized Digest System")
    st.markdown("---")

    # Sidebar for navigation
    with st.sidebar:
        st.header("Navigation")

        # Show pending review count
        db_temp = get_db()
        try:
            pending_review_count = db_temp.query(Digest).filter_by(status='pending_review').count()
        finally:
            db_temp.close()

        # Add badge to review page if there are pending items
        review_page_label = "✅ Admin: Review Digests"
        if pending_review_count > 0:
            review_page_label = f"✅ Admin: Review Digests ({pending_review_count} ⏳)"

        page = st.radio(
            "Select Page",
            ["Home", "Member Onboarding", "Upload Document", "Fetch WordPress Posts", "View Digests", "Manage Interests", "🔧 Admin: Automation", review_page_label]
        )

        st.markdown("---")

        # Current member display
        if st.session_state.current_member:
            st.success(f"👤 Logged in as: {st.session_state.current_member['name']}")
            if st.button("Logout"):
                st.session_state.current_member = None
                st.rerun()
        else:
            st.info("👤 Not logged in")

    # Route to pages
    if page == "Home":
        show_home()
    elif page == "Member Onboarding":
        show_member_onboarding()
    elif page == "Upload Document":
        show_upload_document()
    elif page == "Fetch WordPress Posts":
        show_fetch_wordpress_posts()
    elif page == "View Digests":
        show_view_digests()
    elif page == "Manage Interests":
        show_manage_interests()
    elif page == "🔧 Admin: Automation":
        show_admin_automation()
    elif "✅ Admin: Review Digests" in page:  # Match with or without count badge
        show_admin_review_digests()


def show_home():
    st.header("Welcome to the Personalized Digest System")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🎯 System Features")
        st.markdown("""
        - **Member Onboarding**: Register and select your interest tags
        - **Document Upload**: Upload articles, forums, or documents
        - **AI-Powered Analysis**: LLM extracts relevant topics from content
        - **Personalized Digests**: Get summaries tailored to your interests
        - **Interest Management**: Update your preferences anytime
        """)

    with col2:
        st.subheader("📊 System Stats")
        db = get_db()
        try:
            member_count = db.query(Member).count()
            document_count = db.query(Document).count()
            digest_count = db.query(Digest).count()

            st.metric("Total Members", member_count)
            st.metric("Documents Processed", document_count)
            st.metric("Digests Generated", digest_count)
        finally:
            db.close()

    st.markdown("---")
    st.info("👈 Use the sidebar to navigate through different features")


def show_member_onboarding():
    st.header("👤 Member Onboarding")

    # Check if already logged in
    if st.session_state.current_member:
        st.warning(f"You are already logged in as {st.session_state.current_member['name']}")
        st.info("Logout from the sidebar to create a new account or login as different member")
        return

    tab1, tab2 = st.tabs(["Register New Member", "Login"])

    with tab1:
        st.subheader("Create New Account")

        with st.form("registration_form"):
            name = st.text_input("Full Name*")
            email = st.text_input("Email*")

            st.markdown("### Select Your Interests")
            st.info("Choose topics you're interested in. Your digests will be personalized based on these selections.")

            db = get_db()
            try:
                # Seed default interests if not exists
                seed_default_interests(db)

                # Get all interests
                all_interests = db.query(Interest).all()

                # Create checkboxes for interests
                selected_interests = []
                cols = st.columns(2)
                for idx, interest in enumerate(all_interests):
                    with cols[idx % 2]:
                        if st.checkbox(
                            f"{interest.name}",
                            help=interest.description,
                            key=f"reg_interest_{interest.id}"
                        ):
                            selected_interests.append(interest.id)
            finally:
                db.close()

            submitted = st.form_submit_button("Register")

            if submitted:
                if not name or not email:
                    st.error("Please fill in all required fields")
                elif not selected_interests:
                    st.error("Please select at least one interest")
                else:
                    db = get_db()
                    try:
                        # Check if email exists
                        existing = db.query(Member).filter_by(email=email).first()
                        if existing:
                            st.error("Email already registered!")
                        else:
                            # Create new member
                            member = Member(name=name, email=email)

                            # Add selected interests
                            for interest_id in selected_interests:
                                interest = db.query(Interest).get(interest_id)
                                if interest:
                                    member.interests.append(interest)

                            db.add(member)
                            db.commit()

                            st.success(f"✅ Registration successful! Welcome, {name}!")
                            st.balloons()

                            # Auto login
                            st.session_state.current_member = {
                                'id': member.id,
                                'name': member.name,
                                'email': member.email
                            }
                            st.rerun()
                    finally:
                        db.close()

    with tab2:
        st.subheader("Login to Existing Account")

        db = get_db()
        try:
            members = db.query(Member).all()

            if not members:
                st.info("No members registered yet. Please register first!")
            else:
                member_options = {f"{m.name} ({m.email})": m for m in members}
                selected_member = st.selectbox("Select Your Account", list(member_options.keys()))

                if st.button("Login"):
                    member = member_options[selected_member]
                    st.session_state.current_member = {
                        'id': member.id,
                        'name': member.name,
                        'email': member.email
                    }
                    st.success(f"Welcome back, {member.name}!")
                    st.rerun()
        finally:
            db.close()


def show_upload_document():
    st.header("📄 Upload Document")

    if not st.session_state.current_member:
        st.warning("Please login or register first to upload documents")
        return

    st.info("📝 Upload articles, forum posts, or documents. The system will use **LLM Task #1** to extract relevant interest tags.")

    with st.form("upload_form"):
        title = st.text_input("Document Title*")
        source_type = st.selectbox("Source Type", ["Article", "Forum", "Document"])
        content = st.text_area("Content*", height=300, placeholder="Paste the full content here...")

        submitted = st.form_submit_button("Upload & Process")

        if submitted:
            if not title or not content:
                st.error("Please fill in all required fields")
            else:
                with st.spinner("Processing document... Using LLM to extract interest tags..."):
                    db = get_db()
                    try:
                        # Get available interest tags
                        all_interests = db.query(Interest).all()
                        available_tags = [i.name for i in all_interests]

                        # LLM Task 1: Extract interest tags from content
                        st.write("🤖 **LLM Task #1: Extracting Interest Tags**")
                        extraction_result = llm_service.extract_interest_tags(content, available_tags)

                        st.json(extraction_result)

                        # Create document
                        document = Document(
                            title=title,
                            content=content,
                            source_type=source_type.lower(),
                            extracted_tags=json.dumps(extraction_result)
                        )
                        db.add(document)
                        db.commit()

                        st.success("✅ Document uploaded and processed successfully!")

                        # Show extracted information
                        st.subheader("Extracted Information")
                        st.write(f"**Primary Topic:** {extraction_result.get('primary_topic', 'N/A')}")
                        st.write(f"**Relevant Tags:** {', '.join(extraction_result.get('tags', []))}")
                        st.write(f"**Confidence:** {extraction_result.get('confidence', 'N/A')}")

                        # Ask if user wants to generate digests
                        if st.button("Generate Digests for All Members"):
                            generate_all_digests(db, document, extraction_result)
                    finally:
                        db.close()


def show_fetch_wordpress_posts():
    st.header("🌐 Fetch WordPress Posts")

    if not st.session_state.current_member:
        st.warning("Please login or register first to fetch WordPress posts")
        return

    st.info("📡 Fetch posts from WordPress sites via REST API and automatically process them with AI")

    # WordPress URL input
    wordpress_url = st.text_input(
        "WordPress Site URL",
        value="https://domain1.badev.tools",
        help="Enter the base URL of the WordPress site"
    )

    # Authentication section
    with st.expander("🔐 Authentication (Optional - for private posts)", expanded=False):
        st.write("**WordPress Application Password Authentication**")
        st.info("""
        To fetch private/protected posts, you need:
        1. **Username**: Your WordPress username
        2. **Application Password**: Generate from WordPress Dashboard → Users → Profile → Application Passwords

        Leave blank for public posts only.
        """)

        col1, col2 = st.columns(2)
        with col1:
            wp_username = st.text_input("WordPress Username", value="", help="Your WordPress username")
        with col2:
            wp_app_password = st.text_input(
                "Application Password",
                value="",
                type="password",
                help="WordPress Application Password (not your regular password)"
            )

    col1, col2 = st.columns(2)
    with col1:
        num_posts = st.number_input("Number of Posts to Fetch", min_value=1, max_value=20, value=5)
    with col2:
        page_num = st.number_input("Page Number", min_value=1, value=1)

    if st.button("🔍 Fetch Posts", type="primary"):
        with st.spinner(f"Fetching posts from {wordpress_url}..."):
            try:
                # Initialize fetcher with or without authentication
                if wp_username and wp_app_password:
                    st.success(f"✅ Using authenticated access as: {wp_username}")
                    fetcher = WordPressFetcher(wordpress_url, wp_username, wp_app_password)
                else:
                    st.info("ℹ️ Using public access (no authentication)")
                    fetcher = WordPressFetcher(wordpress_url)

                posts = fetcher.get_posts_with_content(per_page=num_posts, page=page_num)

                if not posts:
                    st.error("No posts found or failed to fetch posts. Please check the URL.")
                    st.session_state.fetched_posts = None
                    return

                # Store posts in session state
                st.session_state.fetched_posts = posts
                st.success(f"✅ Fetched {len(posts)} posts successfully!")

            except Exception as e:
                st.error(f"Error fetching posts: {str(e)}")
                st.session_state.fetched_posts = None

    # Display fetched posts if they exist
    if st.session_state.fetched_posts:
        posts = st.session_state.fetched_posts

        st.subheader("📄 Fetched Posts")

        for idx, post in enumerate(posts):
            with st.expander(f"{idx + 1}. {post['title']}", expanded=False):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"**Date:** {post['date']}")
                    st.write(f"**Link:** {post['link']}")
                    st.write(f"**Content Length:** {post.get('content_length', 0)} characters")

                with col2:
                    if st.button(f"📥 Process This Post", key=f"process_{idx}"):
                        st.session_state.processing_started = True
                        st.session_state.single_post_to_process = idx

                # Show preview of content
                if post.get('scraped_content'):
                    preview = post['scraped_content'][:500] + "..." if len(post['scraped_content']) > 500 else post['scraped_content']
                    st.text_area("Content Preview", preview, height=150, key=f"preview_{idx}")

        # Bulk process option
        st.markdown("---")
        st.info("👆 Click 'Process This Post' for individual posts OR click below to process all at once:")
        if st.button("🚀 Process All Posts with AI", type="primary", key="process_all_btn"):
            st.session_state.processing_started = True
            st.session_state.single_post_to_process = None

    # Process posts if processing was triggered
    if st.session_state.processing_started and st.session_state.fetched_posts:
        st.write("### 🤖 AI Processing Started...")

        if st.session_state.get('single_post_to_process') is not None:
            # Process single post
            idx = st.session_state.single_post_to_process
            process_wordpress_post(st.session_state.fetched_posts[idx])
        else:
            # Process all posts
            process_all_wordpress_posts(st.session_state.fetched_posts)

        # Reset processing flag
        st.session_state.processing_started = False
        st.session_state.single_post_to_process = None


def process_wordpress_post(post):
    """Process a single WordPress post through the AI system."""
    with st.spinner(f"Processing '{post['title']}'..."):
        db = get_db()
        try:
            # Get available interest tags
            all_interests = db.query(Interest).all()
            available_tags = [i.name for i in all_interests]

            content = post.get('scraped_content', '')

            if not content:
                st.error("No content available for this post")
                return

            # LLM Task 1: Extract interest tags
            st.write("🤖 **LLM Task #1: Extracting Interest Tags**")
            extraction_result = llm_service.extract_interest_tags(content, available_tags)
            st.json(extraction_result)

            # Create document
            document = Document(
                title=post['title'],
                content=content,
                source_type='wordpress',
                extracted_tags=json.dumps(extraction_result)
            )
            db.add(document)
            db.commit()

            st.success("✅ Post processed and saved!")

            # Show extracted information
            st.write(f"**Primary Topic:** {extraction_result.get('primary_topic', 'N/A')}")
            st.write(f"**Relevant Tags:** {', '.join(extraction_result.get('tags', []))}")

            # Generate digests
            generate_all_digests(db, document, extraction_result)

        finally:
            db.close()


def process_all_wordpress_posts(posts):
    """Process all fetched WordPress posts."""
    db = get_db()

    # Get members count
    members = db.query(Member).all()
    member_count = len(members)

    if member_count == 0:
        st.error("⚠️ No members found! Please register members first to generate digests.")
        st.write("💡 Go to 'Member Onboarding' page to register first!")
        db.close()
        return

    try:
        # Get available interest tags
        all_interests = db.query(Interest).all()
        available_tags = [i.name for i in all_interests]

        progress_bar = st.progress(0)
        status_text = st.empty()

        # Store results for display
        results = []

        for idx, post in enumerate(posts):
            status_text.text(f"📄 Processing {idx + 1}/{len(posts)}: {post['title']}")

            st.write(f"Title: {post['title']}")

            content = post.get('scraped_content', '')

            st.write(f"📝 Content length: {len(content)} characters")

            if not content:
                st.warning(f"⚠️ Skipping '{post['title']}' - No content available")
                continue

            # LLM Task 1: Extract interest tags
            with st.expander(f"🔍 Post {idx + 1}: {post['title']}", expanded=True):
                st.write("**🤖 LLM Task #1: Extracting Interest Tags**")
                st.write(f"Available tags for extraction: {', '.join(available_tags)}")

                try:
                    st.write("⏳ Calling LLM service...")
                    extraction_result = llm_service.extract_interest_tags(content, available_tags)
                    st.write("✅ LLM responded successfully!")

                    # Display extraction results
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Primary Topic:** {extraction_result.get('primary_topic', 'N/A')}")
                        st.write(f"**Confidence:** {extraction_result.get('confidence', 'N/A')}")
                    with col2:
                        st.write(f"**Extracted Tags:** {', '.join(extraction_result.get('tags', []))}")

                    st.json(extraction_result)
                except Exception as e:
                    st.error(f"❌ Error in tag extraction: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                    continue

            # Create document
            try:
                document = Document(
                    title=post['title'],
                    content=content,
                    source_type='wordpress',
                    extracted_tags=json.dumps(extraction_result)
                )
                db.add(document)
                db.commit()
            except Exception as e:
                st.error(f"❌ Error saving document: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                continue

            # Generate digests for this document
            try:
                digest_count = generate_all_digests(db, document, extraction_result)
                st.write(f"✅ Generated {digest_count} digests for this document")
            except Exception as e:
                st.error(f"❌ Error generating digests: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                continue

            results.append({
                'title': post['title'],
                'tags': extraction_result.get('tags', []),
                'primary_topic': extraction_result.get('primary_topic', 'N/A'),
                'digests_created': digest_count
            })

            progress_bar.progress((idx + 1) / len(posts))
            st.write("---")

        status_text.empty()
        progress_bar.empty()

        # Show summary
        st.success(f"✅ Successfully processed {len(results)} posts!")
        st.balloons()

        # Display summary table
        st.subheader("📊 Processing Summary")
        for idx, result in enumerate(results, 1):
            with st.expander(f"✅ {idx}. {result['title']}", expanded=False):
                st.write(f"**Primary Topic:** {result['primary_topic']}")
                st.write(f"**Tags:** {', '.join(result['tags'])}")
                st.write(f"**Digests Created:** {result['digests_created']}")

        st.info(f"💡 Go to **View Digests** page to see your personalized summaries!")

    finally:
        db.close()


def generate_all_digests(db, document, extraction_result):
    """Generate personalized digests for all members. Returns count of digests created."""
    st.write("🔍 **DEBUG: Entered generate_all_digests function**")

    try:
        members = db.query(Member).all()

        st.write(f"📊 Found {len(members)} members for digest generation")

        if not members:
            st.warning("⚠️ No members found! Please register members first.")
            return 0

        st.info(f"Generating digests for {len(members)} members...")

        document_tags = extraction_result.get('tags', [])

        # Show digest generation details
        digest_details = []

        for idx, member in enumerate(members):
            try:
                member_interest_names = [i.name for i in member.interests]

                # Calculate relevance score
                matching_tags = set(member_interest_names) & set(document_tags)
                relevance_score = len(matching_tags) * 10 + len(member_interest_names)

                # Generate personalized digest using LLM Task 2
                summary = llm_service.generate_personalized_digest(
                    content=document.content,
                    title=document.title,
                    member_interests=member_interest_names,
                    document_tags=document_tags
                )

                # Create digest with pending_review status for admin approval
                digest = Digest(
                    member_id=member.id,
                    document_id=document.id,
                    summary=summary,
                    relevance_score=relevance_score,
                    status='pending_review'  # Require admin review before sending
                )
                db.add(digest)

                digest_details.append({
                    'member': member.name,
                    'interests': member_interest_names,
                    'matching_tags': list(matching_tags),
                    'relevance_score': relevance_score
                })

            except Exception as e:
                st.error(f"❌ Error creating digest for {member.name}: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
        db.commit()

        # Display digest generation summary
        with st.expander("📋 View Digest Details", expanded=True):
            for detail in digest_details:
                st.write(f"**{detail['member']}**: Relevance {detail['relevance_score']}/100 | "
                        f"Matching: {', '.join(detail['matching_tags']) if detail['matching_tags'] else 'None'}")

        # Show approval reminder
        st.success(f"✅ Generated {len(digest_details)} digest(s)")
        st.info("⏳ **Admin Approval Required:** Go to '✅ Admin: Review Digests' page to review and approve before sending emails")

        return len(digest_details)

    except Exception as e:
        st.error(f"❌ Critical error in generate_all_digests: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return 0


def show_view_digests():
    if not st.session_state.current_member:
        st.warning("Please login or register first to view digests")
        return

    db = get_db()
    try:
        member_id = st.session_state.current_member['id']
        member = db.get(Member, member_id)

        # Show member interests
        st.subheader("Your Interests")
        interest_names = [i.name for i in member.interests]
        st.write(", ".join(interest_names) if interest_names else "No interests selected")

        # Show all processed documents with their AI-extracted tags
        st.markdown("---")
        st.subheader("📚 All Processed Documents")
        all_documents = db.query(Document).order_by(Document.uploaded_at.desc()).limit(10).all()

        if all_documents:
            st.success(f"Found {len(all_documents)} processed documents")
            for doc in all_documents:
                try:
                    tags_data = json.loads(doc.extracted_tags)
                    extracted_tags = tags_data.get('tags', [])
                    primary_topic = tags_data.get('primary_topic', 'N/A')

                    st.write(f"**{doc.title}** ({doc.source_type})")
                    st.write(f"   🏷️ Tags: {', '.join(extracted_tags)}")
                    st.write(f"   📌 Topic: {primary_topic}")

                    # Check digests for this document
                    doc_digests = db.query(Digest).filter_by(document_id=doc.id).all()
                    st.write(f"   📊 Digests created: {len(doc_digests)}")
                    st.write("")
                except Exception as e:
                    st.write(f"**{doc.title}** ({doc.source_type}) - Error: {e}")
        else:
            st.warning("No documents found. Please fetch and process WordPress posts first.")

        st.markdown("---")

        # Get digests for this member
        digests = db.query(Digest).filter_by(member_id=member_id).order_by(
            Digest.relevance_score.desc(),
            Digest.created_at.desc()
        ).all()

        if not digests:
            st.info("No digests available yet. Upload some documents to get started!")
            return

        st.subheader(f"Your Digests ({len(digests)})")

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("Filter by Status", ["All", "Draft", "Published"])
        with col2:
            sort_by = st.selectbox("Sort by", ["Relevance (High to Low)", "Date (Newest First)"])

        # Apply filters
        filtered_digests = digests
        if status_filter != "All":
            filtered_digests = [d for d in digests if d.status == status_filter.lower()]

        # Display digests
        for digest in filtered_digests:
            with st.expander(
                f"📄 {digest.document.title} - Relevance: {digest.relevance_score}/100",
                expanded=False
            ):
                # Document info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Source:** {digest.document.source_type.title()}")
                with col2:
                    st.write(f"**Status:** {digest.status.title()}")
                with col3:
                    st.write(f"**Created:** {digest.created_at.strftime('%Y-%m-%d')}")

                # Show extracted tags
                try:
                    tags_data = json.loads(digest.document.extracted_tags)
                    doc_tags = tags_data.get('tags', [])
                    matching = set(interest_names) & set(doc_tags)

                    st.write(f"**Document Tags:** {', '.join(doc_tags)}")
                    if matching:
                        st.write(f"**Matching Your Interests:** ✅ {', '.join(matching)}")
                except:
                    pass

                st.markdown("---")

                # Personalized summary
                st.markdown("### 📝 Your Personalized Summary")
                st.write(digest.summary)

                # Actions
                col1, col2, col3 = st.columns(3)
                with col1:
                    if digest.status == 'draft':
                        if st.button(f"✅ Publish", key=f"publish_{digest.id}"):
                            digest.status = 'published'
                            db.commit()
                            st.success("Published!")
                            st.rerun()
                with col2:
                    if st.button(f"📖 View Full Document", key=f"view_{digest.id}"):
                        st.text_area(
                            "Full Content",
                            digest.document.content,
                            height=300,
                            key=f"content_{digest.id}"
                        )
    finally:
        db.close()


def show_manage_interests():
    st.header("🏷️ Manage Your Interests")

    if not st.session_state.current_member:
        st.warning("Please login or register first to manage interests")
        return

    db = get_db()
    try:
        member_id = st.session_state.current_member['id']
        member = db.get(Member, member_id)
        all_interests = db.query(Interest).all()

        st.info("✏️ Update your interest preferences anytime. Your future digests will be adjusted accordingly.")

        current_interest_ids = [i.id for i in member.interests]

        st.subheader("Select Your Interests")

        # Create checkboxes
        new_selections = []
        cols = st.columns(2)
        for idx, interest in enumerate(all_interests):
            with cols[idx % 2]:
                is_selected = st.checkbox(
                    f"{interest.name}",
                    value=interest.id in current_interest_ids,
                    help=interest.description,
                    key=f"manage_interest_{interest.id}"
                )
                if is_selected:
                    new_selections.append(interest.id)

        if st.button("💾 Save Changes", type="primary"):
            # Clear existing interests
            member.interests.clear()

            # Add new selections
            for interest_id in new_selections:
                interest = db.query(Interest).get(interest_id)
                if interest:
                    member.interests.append(interest)

            db.commit()
            st.success("✅ Interests updated successfully!")
            st.rerun()

        # Show statistics
        st.markdown("---")
        st.subheader("📊 Your Digest Statistics")

        total_digests = db.query(Digest).filter_by(member_id=member_id).count()
        draft_digests = db.query(Digest).filter_by(member_id=member_id, status='draft').count()
        published_digests = db.query(Digest).filter_by(member_id=member_id, status='published').count()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Digests", total_digests)
        with col2:
            st.metric("Draft", draft_digests)
        with col3:
            st.metric("Published", published_digests)

    finally:
        db.close()


def show_admin_automation():
    """Admin page for configuring automated digest generation and email delivery."""
    st.header("🔧 Admin: Digest Automation")

    st.info("💡 Configure automated digest generation and email delivery. The system can fetch WordPress posts, generate digests, and email them to members on a schedule.")

    db = get_db()
    try:
        # Get or create config
        config = db.query(SchedulerConfig).first()
        if not config:
            config = SchedulerConfig()
            db.add(config)
            db.commit()

        # Tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs(["📅 Schedule Configuration", "📧 Email Settings", "📊 Queue Status", "🧪 Test & Run"])

        # Tab 1: Schedule Configuration
        with tab1:
            st.subheader("Schedule Configuration")

            with st.form("schedule_config"):
                enabled = st.checkbox("Enable Automated Digests", value=bool(config.enabled))

                col1, col2 = st.columns(2)
                with col1:
                    schedule_time = st.time_input(
                        "Daily Run Time",
                        value=datetime.strptime(config.schedule_time, '%H:%M').time()
                    )

                with col2:
                    # Parse current days safely
                    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    try:
                        current_days = [day_names[int(d)] for d in config.schedule_days.split(',') if d.strip().isdigit() and 0 <= int(d) <= 6]
                    except:
                        current_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

                    days_selected = st.multiselect(
                        "Run on Days",
                        options=day_names,
                        default=current_days
                    )

                wordpress_url = st.text_input(
                    "WordPress Site URL",
                    value=config.wordpress_url or '',
                    placeholder="https://example.com"
                )

                col1, col2 = st.columns(2)
                with col1:
                    posts_per_run = st.number_input(
                        "Posts to Fetch Per Run",
                        min_value=1,
                        max_value=20,
                        value=config.posts_per_run
                    )

                with col2:
                    send_immediately = st.checkbox(
                        "Send Emails Immediately",
                        value=bool(config.send_immediately),
                        help="If checked, emails will be sent immediately after digest generation. Otherwise, they'll be queued for manual processing."
                    )

                submitted = st.form_submit_button("💾 Save Configuration", use_container_width=True)

                if submitted:
                    # Validation
                    if not days_selected:
                        st.error("❌ Please select at least one day")
                        return

                    # Convert days to numbers (0=Monday)
                    day_map = {'Monday': '0', 'Tuesday': '1', 'Wednesday': '2', 'Thursday': '3',
                              'Friday': '4', 'Saturday': '5', 'Sunday': '6'}
                    schedule_days = ','.join([day_map[d] for d in days_selected])

                    config.enabled = 1 if enabled else 0
                    config.schedule_time = schedule_time.strftime('%H:%M')
                    config.schedule_days = schedule_days
                    config.wordpress_url = wordpress_url
                    config.posts_per_run = posts_per_run
                    config.send_immediately = 1 if send_immediately else 0
                    config.updated_at = datetime.now(timezone.utc)

                    log.section("Saving Scheduler Configuration")
                    log.info(f"Enabled: {enabled}", indent=1)
                    log.info(f"Schedule: {config.schedule_time} on days {schedule_days}", indent=1)
                    log.info(f"WordPress URL: {wordpress_url or 'Not set'}", indent=1)
                    log.info(f"Posts per run: {posts_per_run}", indent=1)
                    log.info(f"Send immediately: {send_immediately}", indent=1)

                    try:
                        db.commit()
                        log.success("Configuration saved to database")
                        st.success("✅ Configuration saved successfully!")
                        st.rerun()
                    except Exception as e:
                        log.error(f"Failed to save configuration: {str(e)}")
                        st.error(f"❌ Failed to save: {str(e)}")
                        db.rollback()

            # Show current status
            st.markdown("---")
            st.subheader("Current Status")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Status", "Enabled ✅" if config.enabled else "Disabled ❌")
            with col2:
                if config.last_run:
                    st.metric("Last Run", config.last_run.strftime('%Y-%m-%d %H:%M'))
                else:
                    st.metric("Last Run", "Never")
            with col3:
                if config.next_run:
                    st.metric("Next Run", config.next_run.strftime('%Y-%m-%d %H:%M'))
                else:
                    st.metric("Next Run", "Not scheduled")

        # Tab 2: Email Settings
        with tab2:
            st.subheader("Email Configuration")

            st.markdown("""
            Configure your email settings in the `.env` file:

            ```bash
            # SMTP Configuration
            SMTP_HOST=smtp.gmail.com
            SMTP_PORT=587
            SMTP_USERNAME=your-email@gmail.com
            SMTP_PASSWORD=your-app-password
            FROM_EMAIL=your-email@gmail.com
            FROM_NAME=Personalized Digest System

            # Branding
            BRAND_NAME=My Digest
            BRAND_COLOR=#4F46E5
            LOGO_URL=https://example.com/logo.png
            SUPPORT_EMAIL=support@example.com
            ```
            """)

            # Test email connection
            email_service = EmailService()
            if st.button("🧪 Test Email Connection"):
                with st.spinner("Testing SMTP connection..."):
                    success, message = email_service.test_connection()
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")

        # Tab 3: Queue Status
        with tab3:
            st.subheader("Email Queue Status")

            # Get queue statistics
            pending = db.query(EmailQueue).filter_by(status='pending').count()
            sent = db.query(EmailQueue).filter_by(status='sent').count()
            failed = db.query(EmailQueue).filter_by(status='failed').count()
            retry = db.query(EmailQueue).filter_by(status='retry').count()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("⏳ Pending", pending)
            with col2:
                st.metric("✅ Sent", sent)
            with col3:
                st.metric("❌ Failed", failed)
            with col4:
                st.metric("🔄 Retry", retry)

            # Process queue button
            if pending > 0 or retry > 0:
                if st.button("📧 Process Email Queue Now", use_container_width=True):
                    with st.spinner(f"Processing {pending + retry} emails..."):
                        processor = EmailQueueProcessor()
                        stats = processor.process_queue()

                        st.success(f"✅ Processed {stats['processed']} emails")
                        st.write(f"• Sent: {stats['sent']}")
                        st.write(f"• Failed: {stats['failed']}")

                        if stats['errors']:
                            with st.expander("View Errors"):
                                for error in stats['errors']:
                                    st.error(f"{error['email']}: {error['error']}")

                        st.rerun()

            # Show recent emails
            st.markdown("---")
            st.subheader("Recent Emails")
            recent_emails = db.query(EmailQueue).order_by(EmailQueue.created_at.desc()).limit(10).all()

            if recent_emails:
                for email in recent_emails:
                    with st.expander(f"{email.recipient_email} - {email.status.upper()}"):
                        st.write(f"**Subject:** {email.subject}")
                        st.write(f"**Status:** {email.status}")
                        st.write(f"**Priority:** {email.priority}")
                        st.write(f"**Attempts:** {email.attempts}/{email.max_attempts}")
                        st.write(f"**Scheduled:** {email.scheduled_at}")
                        if email.sent_at:
                            st.write(f"**Sent:** {email.sent_at}")
                        if email.error_message:
                            st.error(f"**Error:** {email.error_message}")
            else:
                st.info("No emails in queue")

        # Tab 4: Test & Run
        with tab4:
            st.subheader("Manual Testing & Execution")

            st.warning("⚠️ These actions will run immediately. Use for testing only.")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("🚀 Run Digest Generation Now", use_container_width=True):
                    with st.spinner("Running digest generation..."):
                        scheduler = DigestScheduler()
                        scheduler.run_now()
                        st.success("✅ Digest generation completed!")
                        st.rerun()

            with col2:
                if st.button("📧 Process Email Queue Now", use_container_width=True):
                    with st.spinner("Processing email queue..."):
                        processor = EmailQueueProcessor()
                        stats = processor.process_queue()
                        st.success(f"✅ Processed {stats['sent']} emails")
                        st.rerun()

            st.markdown("---")
            st.subheader("📚 Setup Instructions")

            # Show log file location
            from pathlib import Path
            log_dir = Path("logs")
            log_file = log_dir / f"digest_{datetime.now().strftime('%Y%m%d')}.log"

            if log_file.exists():
                # Show recent log entries
                with st.expander("View Recent Logs (Last 50 lines)"):
                    try:
                        with open(log_file, 'r') as f:
                            lines = f.readlines()
                            recent_lines = lines[-50:] if len(lines) > 50 else lines
                            st.code(''.join(recent_lines), language='log')
                    except Exception as e:
                        st.error(f"Error reading log file: {e}")
            else:
                st.info(f"📝 Logs will be saved to: `{log_file.absolute()}`")

            st.markdown("---")

    finally:
        db.close()


def show_admin_review_digests():
    """
    Admin page for reviewing AI-generated digests before they are sent.
    Task 4: Safety review to minimize brand risk.
    """
    st.header("✅ Admin: Review AI-Generated Digests")

    st.info("""
    **🛡️ Content Safety Review**

    Review AI-generated digest summaries before they are sent to members. This helps ensure:
    - Content is appropriate and accurate
    - No sensitive or inappropriate information
    - Brand voice and quality standards are maintained
    - No AI hallucinations or errors
    """)

    db = get_db()
    try:
        # Get counts for each status
        pending_count = db.query(Digest).filter_by(status='pending_review').count()
        approved_count = db.query(Digest).filter_by(status='approved').count()
        rejected_count = db.query(Digest).filter_by(status='rejected').count()

        # Show stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("⏳ Pending Review", pending_count)
        with col2:
            st.metric("✅ Approved", approved_count)
        with col3:
            st.metric("❌ Rejected", rejected_count)

        st.markdown("---")

        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["⏳ Pending Review", "✅ Approved", "❌ Rejected"])

        # Tab 1: Pending Review
        with tab1:
            st.subheader(f"Digests Pending Review ({pending_count})")

            if pending_count == 0:
                st.success("🎉 No digests pending review! All caught up.")
            else:
                # Bulk actions
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.info(f"📋 {pending_count} digest(s) waiting for your review")
                with col2:
                    if st.button("🔄 Refresh", use_container_width=True):
                        st.rerun()

                st.markdown("---")

                # Get pending digests
                pending_digests = db.query(Digest).filter_by(status='pending_review').order_by(
                    Digest.created_at.desc()
                ).all()

                # Review each digest
                for idx, digest in enumerate(pending_digests):
                    with st.expander(
                        f"📄 Digest #{digest.id} - {digest.document.title[:60]}... → {digest.member.name}",
                        expanded=(idx == 0)  # Expand first one by default
                    ):
                        # Show digest details
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.markdown(f"**Document Title:** {digest.document.title}")
                            st.markdown(f"**Recipient:** {digest.member.name} ({digest.member.email})")

                        with col2:
                            st.markdown(f"**Relevance Score:** {digest.relevance_score}")
                            st.markdown(f"**Created:** {digest.created_at.strftime('%Y-%m-%d %H:%M')}")

                        # Member interests
                        member_interests = [i.name for i in digest.member.interests]
                        st.markdown(f"**Member Interests:** {', '.join(member_interests)}")

                        # Document tags
                        if digest.document.extracted_tags:
                            try:
                                tags_data = json.loads(digest.document.extracted_tags)
                                doc_tags = tags_data.get('tags', [])
                                st.markdown(f"**Document Tags:** {', '.join(doc_tags)}")
                            except:
                                pass

                        st.markdown("---")

                        # Show AI-generated summary
                        st.markdown("### 📝 AI-Generated Summary")
                        st.markdown(f"> {digest.summary}")

                        st.markdown("---")

                        # Show original content preview
                        with st.expander("📖 View Original Document Content"):
                            st.text_area(
                                "Full Content",
                                digest.document.content,
                                height=200,
                                key=f"content_{digest.id}",
                                disabled=True
                            )

                        st.markdown("---")

                        # Review actions
                        st.markdown("### 🔍 Review Decision")

                        col1, col2, col3 = st.columns([2, 2, 2])

                        with col1:
                            if st.button(
                                "✅ Approve & Queue Email",
                                key=f"approve_{digest.id}",
                                type="primary",
                                use_container_width=True
                            ):
                                # Update digest status
                                digest.status = 'approved'
                                digest.reviewed_at = datetime.now(timezone.utc)
                                digest.reviewed_by = 'Admin'  # Could be enhanced with actual user tracking

                                # Queue email for sending
                                processor = EmailQueueProcessor()
                                processor.queue_digest_email(db, digest)

                                db.commit()

                                st.success(f"✅ Digest approved and email queued for {digest.member.email}")
                                st.info("💡 Go to 'Admin: Automation' → 'Queue Status' to send emails")
                                st.rerun()

                        with col2:
                            if st.button(
                                "❌ Reject",
                                key=f"reject_{digest.id}",
                                use_container_width=True
                            ):
                                # Show rejection reason input
                                st.session_state[f'show_reject_{digest.id}'] = True
                                st.rerun()

                        with col3:
                            if st.button(
                                "⏭️ Skip for Now",
                                key=f"skip_{digest.id}",
                                use_container_width=True
                            ):
                                st.info("Skipped - will remain in pending review")

                        # Rejection reason dialog
                        if st.session_state.get(f'show_reject_{digest.id}', False):
                            st.markdown("---")
                            rejection_reason = st.text_area(
                                "Rejection Reason (optional)",
                                placeholder="Why is this digest being rejected? (e.g., inappropriate content, inaccurate summary, poor quality)",
                                key=f"rejection_reason_{digest.id}"
                            )

                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(
                                    "Confirm Rejection",
                                    key=f"confirm_reject_{digest.id}",
                                    type="primary",
                                    use_container_width=True
                                ):
                                    digest.status = 'rejected'
                                    digest.reviewed_at = datetime.now(timezone.utc)
                                    digest.reviewed_by = 'Admin'
                                    digest.rejection_reason = rejection_reason or "No reason provided"
                                    db.commit()

                                    st.success(f"❌ Digest rejected")
                                    del st.session_state[f'show_reject_{digest.id}']
                                    st.rerun()

                            with col2:
                                if st.button(
                                    "Cancel",
                                    key=f"cancel_reject_{digest.id}",
                                    use_container_width=True
                                ):
                                    del st.session_state[f'show_reject_{digest.id}']
                                    st.rerun()

                        st.markdown("---")

        # Tab 2: Approved
        with tab2:
            st.subheader(f"Approved Digests ({approved_count})")

            if approved_count == 0:
                st.info("No approved digests yet")
            else:
                approved_digests = db.query(Digest).filter_by(status='approved').order_by(
                    Digest.reviewed_at.desc()
                ).limit(20).all()

                for digest in approved_digests:
                    with st.expander(
                        f"✅ {digest.document.title[:50]}... → {digest.member.name}"
                    ):
                        st.markdown(f"**Reviewed:** {digest.reviewed_at.strftime('%Y-%m-%d %H:%M')}")
                        st.markdown(f"**Reviewed by:** {digest.reviewed_by}")
                        st.markdown(f"**Recipient:** {digest.member.email}")
                        st.markdown("---")
                        st.markdown("**Summary:**")
                        st.markdown(f"> {digest.summary}")

        # Tab 3: Rejected
        with tab3:
            st.subheader(f"Rejected Digests ({rejected_count})")

            if rejected_count == 0:
                st.info("No rejected digests")
            else:
                rejected_digests = db.query(Digest).filter_by(status='rejected').order_by(
                    Digest.reviewed_at.desc()
                ).limit(20).all()

                for digest in rejected_digests:
                    with st.expander(
                        f"❌ {digest.document.title[:50]}... → {digest.member.name}"
                    ):
                        st.markdown(f"**Reviewed:** {digest.reviewed_at.strftime('%Y-%m-%d %H:%M')}")
                        st.markdown(f"**Reviewed by:** {digest.reviewed_by}")
                        st.markdown(f"**Recipient:** {digest.member.email}")

                        if digest.rejection_reason:
                            st.warning(f"**Rejection Reason:** {digest.rejection_reason}")

                        st.markdown("---")
                        st.markdown("**Summary:**")
                        st.markdown(f"> {digest.summary}")

                        # Option to re-review
                        if st.button(
                            "🔄 Move Back to Pending Review",
                            key=f"unreject_{digest.id}",
                            use_container_width=True
                        ):
                            digest.status = 'pending_review'
                            digest.reviewed_at = None
                            digest.reviewed_by = None
                            digest.rejection_reason = None
                            db.commit()
                            st.success("Moved back to pending review")
                            st.rerun()

    finally:
        db.close()


if __name__ == "__main__":
    main()